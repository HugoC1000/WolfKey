"""Simpler timetable schedule generator.

This module focuses on producing reliable possible schedule combinations
from Course -> Block relations. It intentionally prefers a clear,
deterministic backtracking approach over advanced matching algorithms so
the behaviour is easy to reason about and constraints (especially
required courses) are handled correctly.

API:
 - generate_possible_schedules(requested_course_ids, required_course_ids=None, max_schedules=20)

Returned schedule shape matches the previous conventions:
{
  'name': str,
  'mapping': { course_id: {'block': block_code, 'course_name': name}, ... },
  'blocks': { block_code: [ {id, name}, ... ], ... },
  'matched_courses': int
}
"""

from typing import List, Dict, Optional, Set
from forum.models import Course
from forum.serializers.user import USER_SCHEDULE_BLOCKS

ALL_BLOCKS = USER_SCHEDULE_BLOCKS


def generate_possible_schedules(requested_course_ids: List[int],
                                required_course_ids: Optional[List[int]] = None,
                                max_schedules: int = 20) -> List[Dict]:
    # Load courses and their available blocks
    courses_qs = Course.objects.filter(id__in=requested_course_ids).prefetch_related('blocks')
    if not courses_qs:
        return []

    course_by_id = {c.id: c for c in courses_qs}
    course_blocks = {c.id: [b.code for b in c.blocks.all()] for c in courses_qs}

    required_set = set(required_course_ids or []) & set(course_by_id.keys())
    optional_ids = [cid for cid in requested_course_ids if cid in course_by_id and cid not in required_set]
    ordered_ids = list(required_set) + optional_ids

    # Feasibility check: required courses must have at least one block
    if any(not course_blocks[rid] for rid in required_set):
        return []

    schedules = []
    seen_signatures = set()

    def record(assign: Dict[int, str]):
        sig = tuple(sorted(assign.items()))
        if sig in seen_signatures:
            return
        seen_signatures.add(sig)

        blocks = {b: [] for b in ALL_BLOCKS}
        mapping = {}
        for cid, blk in assign.items():
            course = course_by_id[cid]
            mapping[cid] = {'block': blk, 'course_name': course.name}
            blocks[blk].append({'id': cid, 'name': course.name})

        schedules.append({
            'name': f'Schedule Option {len(schedules)+1} ({len(assign)} courses)',
            'mapping': mapping,
            'blocks': blocks,
            'matched_courses': len(assign)
        })

    def backtrack(idx: int, assign: Dict[int, str], used_blocks: Set[str]):
        if idx >= len(ordered_ids):
            if required_set.issubset(assign.keys()):
                record(assign.copy())
            return

        cid = ordered_ids[idx]
        available = [b for b in course_blocks.get(cid, []) if b not in used_blocks]

        if cid in required_set:
            for blk in available:
                assign[cid] = blk
                used_blocks.add(blk)
                backtrack(idx + 1, assign, used_blocks)
                used_blocks.remove(blk)
                del assign[cid]
        else:
            for blk in available:
                assign[cid] = blk
                used_blocks.add(blk)
                backtrack(idx + 1, assign, used_blocks)
                used_blocks.remove(blk)
                del assign[cid]
            # try skipping optional
            backtrack(idx + 1, assign, used_blocks)

    backtrack(0, {}, set())

    # Fallback empty schedule if no required courses
    if not schedules and not required_set:
        blocks = {b: [] for b in ALL_BLOCKS}
        schedules.append({'name': 'Empty schedule', 'mapping': {}, 'blocks': blocks, 'matched_courses': 0})

    # Sort schedules by number of requested matches (descending)
    requested_set = set(requested_course_ids)
    schedules.sort(key=lambda sch: len(requested_set & set(sch['mapping'].keys())), reverse=True)

    # Limit to max_schedules
    return schedules[:max_schedules]


def evaluate_multiple_schedules(requested_course_ids: List[int], schedules_list: List[Dict]) -> List[Dict]:
    """Score candidate schedules by how many requested courses they satisfy.

    This helper is lightweight: it counts how many requested IDs appear in the
    schedule mapping and returns the candidate schedules annotated with that
    count, sorted by descending match count.
    """
    results = []
    requested_set = set(requested_course_ids)
    for sch in schedules_list:
        mapping = sch.get('mapping', {})
        matched = len(requested_set & set(mapping.keys()))
        results.append({'matching': matched, 'schedule': sch})

    results.sort(key=lambda r: r['matching'], reverse=True)
    return results
