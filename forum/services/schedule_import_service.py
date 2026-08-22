"""Extract, match, and apply imported student schedules."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from django.db import transaction
from django.conf import settings

from forum.models import Course
from forum.serializers.user import USER_SCHEDULE_BLOCKS, UserScheduleSerializer
from forum.services.course_services import search_courses


MAX_SCHEDULE_TEXT_LENGTH = 20_000
MAX_SCHEDULE_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_SCHEDULE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

IGNORED_COURSE_NAMES = {"flex", "activities", "academics", "peaks", "advisory"}
AP_ECONOMICS_PATTERN = re.compile(
    r"\bap\b.*\b(?:microeconomics|macroeconomics|micro\s*(?:and|&|/)\s*macro)\b",
    re.IGNORECASE,
)
AP_PHYSICS_C_PATTERN = re.compile(
    r"\bap\s+physics\s+c\b(?:\s*[:\-]?\s*(?:mechanics|electricity\s*(?:and|&)\s*magnetism|e\s*(?:and|&)\s*m))?\b",
    re.IGNORECASE,
)
AP_ENGLISH_LANGUAGE_PATTERN = re.compile(
    r"\bap\s+(?:english\s+)?(?:lang(?:uage)?(?:\s+and\s+composition)?|language\s+and\s+composition)\b",
    re.IGNORECASE,
)
AP_ENGLISH_LANGUAGE_AND_LITERATURE_PATTERN = re.compile(
    r"\bap\s+english\s+(?:lang(?:uage)?\s+and\s+lit(?:erature)?|language\s+and\s+literature)\b",
    re.IGNORECASE,
)


class ScheduleImportError(Exception):
    """Base exception for schedule import failures."""


class ScheduleImportConfigurationError(ScheduleImportError):
    """Raised when the Gemini integration is not configured."""


class ScheduleImportProviderError(ScheduleImportError):
    """Raised when Gemini cannot return usable structured output."""


class ScheduleImportValidationError(ScheduleImportError):
    """Raised when imported or reviewed schedule data is invalid."""


@dataclass(frozen=True)
class ExtractedCourse:
    course_name: str
    block: str


SCHEDULE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "courses": {
            "type": "array",
            "maxItems": 9,
            "items": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title only, without a class code, URL, or block suffix.",
                    },
                    "block": {
                        "type": "string",
                        "enum": list(USER_SCHEDULE_BLOCKS),
                        "description": "The canonical schedule block for this course.",
                    },
                },
                "required": ["course_name", "block"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["courses"],
    "additionalProperties": False,
}


SCHEDULE_EXTRACTION_PROMPT = """
Extract the student's academic courses and their schedule blocks from the supplied
schedule. Return only data matching the provided JSON schema.

Rules:
- Valid blocks are exactly: 1A, 1B, 1D, 1E, 2A, 2B, 2C, 2D, 2E.
- For screenshots, treat every individual class card/row as a separate course.
  Never combine neighboring cards, columns, or rows into one course name, and
  never join two course names with "/".
- Return the human course title only. Remove hyperlinks, class/section codes, and
  repeated parenthesized blocks. For example,
  "AP Calculus BC - APCAL12A-2C (2C)" becomes course_name "AP Calculus BC"
  and block "2C".
- Prefer the block suffix in the card's class code (for example, "-2E" or
  "(2E)") over the card's visual position. The block belongs only to that card.
- In a screenshot with multiple columns, read each card's complete title and
  class code before moving to the next card. A card such as "Chemistry 12 - CH
  12-2E" must be returned as course_name "Chemistry 12" and block "2E".
- Ignore Flex, Activities, Academics, PEAKS, and Advisory entries.
- Teacher Assistant 10, Teacher Assistant 11, and Teacher Assistant 12 are one
  course. Always return the course name exactly as "Teacher Assistant" (without
  the grade number), preserving the detected block.
- AP Microeconomics and AP Macroeconomics are two appearances of one course.
  Return that course once as "AP Economics".
- AP Physics C Mechanics and AP Physics C Electricity and Magnetism (including
  "AP Physics C E and M") are one course. Return either as "AP Physics C".
- If AP English Lang and Lit / AP English Language and Literature appears,
  ignore English Studies 12 entirely.
- Return AP Language and Composition as "AP English Language".
- Do not invent missing courses or blocks.
""".strip()


def _clean_course_name(value: object) -> str:
    name = str(value or "").strip()
    markdown_match = re.fullmatch(r"\[([^]]+)]\([^)]*\)", name)
    if markdown_match:
        name = markdown_match.group(1)
    name = re.sub(r"^#{1,6}\s*", "", name).strip()
    name = re.sub(r"\s*\(\s*[12](?:A|B|C|D|E)\s*\)\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(
        r"\s+-\s+[A-Z0-9][A-Z0-9._-]*\s*(?:\([12](?:A|B|C|D|E)\))?\s*$",
        "",
        name,
    ).strip()
    if AP_ECONOMICS_PATTERN.search(name):
        return "AP Economics"
    if AP_PHYSICS_C_PATTERN.search(name):
        return "AP Physics C"
    if AP_ENGLISH_LANGUAGE_AND_LITERATURE_PATTERN.search(name):
        return "AP English Language and Literature"
    if AP_ENGLISH_LANGUAGE_PATTERN.search(name):
        return "AP English Language"
    if re.fullmatch(r"teacher\s+assistant\s+(?:10|11|12)", name, flags=re.IGNORECASE):
        return "Teacher Assistant"
    return re.sub(r"\s+", " ", name)


def _normalize_block(value: object) -> Optional[str]:
    match = re.fullmatch(r"\s*\(?\s*([12][A-E])\s*\)?\s*", str(value or ""), re.IGNORECASE)
    if not match:
        return None
    block = match.group(1).upper()
    return block if block in USER_SCHEDULE_BLOCKS else None


def _is_ignored_course(name: str) -> bool:
    normalized = re.sub(r"[^a-z]+", " ", name.casefold()).strip()
    return any(normalized == ignored or normalized.startswith(f"{ignored} ") for ignored in IGNORED_COURSE_NAMES)


def normalize_extracted_courses(raw_courses: Iterable[dict]) -> dict:
    """Validate model rows and group them into at most one course per block."""
    rows_by_block: dict[str, ExtractedCourse] = {}
    conflicts: dict[str, list[str]] = {}
    ignored: list[str] = []

    for raw_course in raw_courses:
        if not isinstance(raw_course, dict):
            continue
        course_name = _clean_course_name(raw_course.get("course_name"))
        block = _normalize_block(raw_course.get("block"))
        if not course_name or not block:
            continue
        if _is_ignored_course(course_name):
            if course_name not in ignored:
                ignored.append(course_name)
            continue

        existing = rows_by_block.get(block)
        if existing and existing.course_name.casefold() != course_name.casefold():
            conflict_names = conflicts.setdefault(block, [existing.course_name])
            if course_name not in conflict_names:
                conflict_names.append(course_name)
            continue
        rows_by_block[block] = ExtractedCourse(course_name=course_name, block=block)

    if any(AP_ENGLISH_LANGUAGE_AND_LITERATURE_PATTERN.search(course.course_name)
           for course in rows_by_block.values()):
        for block, course in list(rows_by_block.items()):
            if course.course_name.casefold() == "english studies 12":
                rows_by_block.pop(block)
                if course.course_name not in ignored:
                    ignored.append(course.course_name)

    for block in conflicts:
        rows_by_block.pop(block, None)

    return {
        "courses": [rows_by_block[block] for block in USER_SCHEDULE_BLOCKS if block in rows_by_block],
        "conflicts": conflicts,
        "ignored": ignored,
    }


def extract_schedule_with_gemini(*, text: Optional[str] = None, image_bytes: Optional[bytes] = None,
                                 mime_type: Optional[str] = None) -> dict:
    """Send one text or image source to Gemini and normalize its structured output."""
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise ScheduleImportConfigurationError(
            "Schedule import is not configured. Set GEMINI_API_KEY and restart the server."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ScheduleImportConfigurationError("The Gemini SDK is not installed.") from exc

    model = getattr(settings, "SCHEDULE_IMPORT_GEMINI_MODEL", "gemini-3.5-flash-lite")
    if text is not None:
        contents = f"{SCHEDULE_EXTRACTION_PROMPT}\n\nSchedule text:\n{text}"
    else:
        contents = [
            types.Part.from_text(text=SCHEDULE_EXTRACTION_PROMPT),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ]

    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": SCHEDULE_RESPONSE_SCHEMA,
                },
            )
        payload = json.loads(response.text)
        raw_courses = payload.get("courses", [])
        if not isinstance(raw_courses, list):
            raise ValueError("Gemini returned a non-list courses value")
        return normalize_extracted_courses(raw_courses)
    except ScheduleImportError:
        raise
    except Exception as exc:
        raise ScheduleImportProviderError("The schedule could not be read. Please try again.") from exc


def _serialize_course(course: Optional[Course]) -> Optional[dict]:
    if not course:
        return None
    return {
        "id": course.id,
        "name": course.name,
        "category": course.category,
    }


def build_schedule_preview(extracted: dict,
                           search_fn: Callable[[str, int], list[Course]] = search_courses) -> dict:
    """Match extracted names to courses and return all nine review rows."""
    extracted_by_block = {course.block: course for course in extracted["courses"]}
    conflicts = extracted.get("conflicts", {})
    review_rows = []

    for block in USER_SCHEDULE_BLOCKS:
        row = {
            "block": block,
            "extracted_name": None,
            "course": None,
            "suggestions": [],
            "status": "missing",
        }

        if block in conflicts:
            row.update({
                "extracted_name": " / ".join(conflicts[block]),
                "status": "conflict",
            })
        elif block in extracted_by_block:
            extracted_course = extracted_by_block[block]
            candidates = list(search_fn(extracted_course.course_name, 5))
            serialized_candidates = [_serialize_course(candidate) for candidate in candidates]
            row.update({
                "extracted_name": extracted_course.course_name,
                "suggestions": serialized_candidates,
                "status": "needs_review",
            })
            if candidates:
                row["course"] = serialized_candidates[0]
                row["status"] = "matched"

        review_rows.append(row)

    return {
        "blocks": review_rows,
        "ignored": extracted.get("ignored", []),
        "summary": {
            "matched": sum(row["status"] == "matched" for row in review_rows),
            "unresolved": sum(row["status"] in {"needs_review", "conflict"} for row in review_rows),
        },
    }


def replace_user_schedule(profile, assignments: dict, *, allow_empty: bool = False) -> dict:
    """Replace all nine profile blocks with validated course IDs or null."""
    if not isinstance(assignments, dict):
        raise ScheduleImportValidationError("Assignments must be an object keyed by block.")

    expected_blocks = set(USER_SCHEDULE_BLOCKS)
    received_blocks = set(assignments)
    if received_blocks != expected_blocks:
        missing = sorted(expected_blocks - received_blocks)
        unknown = sorted(received_blocks - expected_blocks)
        details = []
        if missing:
            details.append(f"missing blocks: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown blocks: {', '.join(unknown)}")
        raise ScheduleImportValidationError("All nine blocks are required (" + "; ".join(details) + ").")

    course_ids = {value for value in assignments.values() if value not in (None, "")}
    try:
        normalized_ids = {int(course_id) for course_id in course_ids}
    except (TypeError, ValueError) as exc:
        raise ScheduleImportValidationError("Every course must be a numeric ID or null.") from exc
    if not normalized_ids and not allow_empty:
        raise ScheduleImportValidationError("Select at least one course before replacing your schedule.")

    courses = Course.objects.in_bulk(normalized_ids)
    if set(courses) != normalized_ids:
        raise ScheduleImportValidationError("One or more selected courses no longer exist.")

    normalized_assignments = {}
    for block in USER_SCHEDULE_BLOCKS:
        value = assignments[block]
        if value in (None, ""):
            normalized_assignments[block] = None
            continue
        course = courses[int(value)]
        normalized_assignments[block] = course

    update_fields = [f"block_{block}" for block in USER_SCHEDULE_BLOCKS]
    with transaction.atomic():
        for block, course in normalized_assignments.items():
            setattr(profile, f"block_{block}", course)
        profile.save(update_fields=update_fields)

    return UserScheduleSerializer(profile).data["schedule"]
