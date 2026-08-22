import json
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from forum.models import Block, Course, User
from forum.serializers.user import USER_SCHEDULE_BLOCKS
from forum.services.schedule_import_service import (
    ExtractedCourse,
    ScheduleImportValidationError,
    build_schedule_preview,
    normalize_extracted_courses,
    replace_user_schedule,
)


class ScheduleImportServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            school_email="schedule-import@wpga.ca",
            password="password123",
            first_name="Schedule",
            last_name="Importer",
        )
        self.blocks = {code: Block.objects.create(code=code) for code in USER_SCHEDULE_BLOCKS}

    def make_course(self, name, *blocks):
        course = Course.objects.create(name=name)
        course.blocks.add(*(self.blocks[block] for block in blocks))
        return course

    def test_normalization_cleans_wolfnet_links_ignores_non_courses_and_combines_economics(self):
        normalized = normalize_extracted_courses([
            {
                "course_name": "[AP Calculus BC - APCAL12A-2C (2C)](https://example.com/class)",
                "block": "(2c)",
            },
            {"course_name": "Advisory", "block": "1A"},
            {"course_name": "Teacher Assistant 10", "block": "1A"},
            {"course_name": "Teacher Assistant 11", "block": "1B"},
            {"course_name": "Teacher Assistant 12", "block": "1D"},
            {"course_name": "AP Microeconomics", "block": "1E"},
            {"course_name": "AP Macroeconomics", "block": "1E"},
        ])

        self.assertEqual(
            [(course.course_name, course.block) for course in normalized["courses"]],
            [
                ("Teacher Assistant", "1A"),
                ("Teacher Assistant", "1B"),
                ("Teacher Assistant", "1D"),
                ("AP Economics", "1E"),
                ("AP Calculus BC", "2C"),
            ],
        )
        self.assertEqual(normalized["ignored"], ["Advisory"])
        self.assertEqual(normalized["conflicts"], {})

    def test_normalization_marks_two_different_courses_in_one_block_as_conflict(self):
        normalized = normalize_extracted_courses([
            {"course_name": "AP Biology", "block": "2D"},
            {"course_name": "AP French", "block": "2D"},
        ])

        self.assertEqual(normalized["courses"], [])
        self.assertEqual(normalized["conflicts"]["2D"], ["AP Biology", "AP French"])

    def test_normalization_canonicalizes_physics_and_ap_english_precedence(self):
        normalized = normalize_extracted_courses([
            {"course_name": "AP Physics C: Mechanics", "block": "1A"},
            {"course_name": "AP Physics C E and M", "block": "1B"},
            {"course_name": "AP Language and Composition", "block": "1D"},
            {"course_name": "AP English Lang and Lit", "block": "1E"},
            {"course_name": "English Studies 12", "block": "2A"},
        ])

        self.assertEqual(
            [(course.course_name, course.block) for course in normalized["courses"]],
            [
                ("AP Physics C", "1A"),
                ("AP Physics C", "1B"),
                ("AP English Language", "1D"),
                ("AP English Language and Literature", "1E"),
            ],
        )
        self.assertEqual(normalized["ignored"], ["English Studies 12"])

    def test_preview_matches_top_name_result_without_using_course_blocks(self):
        wrong_block = self.make_course("AP Calculus BC Wrong", "1A")
        valid_course = self.make_course("AP Calculus BC", "2C")
        queries = []

        def fake_search(query, limit):
            queries.append((query, limit))
            return [wrong_block, valid_course]

        preview = build_schedule_preview(
            {"courses": [ExtractedCourse("AP Calculus BC", "2C")], "conflicts": {}, "ignored": []},
            search_fn=fake_search,
        )
        row = next(item for item in preview["blocks"] if item["block"] == "2C")

        self.assertEqual(queries, [("AP Calculus BC", 5)])
        self.assertEqual(row["status"], "matched")
        self.assertEqual(row["course"]["id"], wrong_block.id)
        self.assertNotIn("blocks", row["course"])
        self.assertNotIn("current_course", row)
        self.assertNotIn("will_clear", row)
        self.assertEqual([course["id"] for course in row["suggestions"]], [wrong_block.id, valid_course.id])

    def test_replacement_clears_every_missing_block(self):
        old_course = self.make_course("Old Course", "1A")
        imported_course = self.make_course("Imported Course", "2C")
        profile = self.user.userprofile
        profile.block_1A = old_course
        profile.save()
        assignments = {block: None for block in USER_SCHEDULE_BLOCKS}
        assignments["2C"] = imported_course.id

        schedule = replace_user_schedule(profile, assignments)
        profile.refresh_from_db()

        self.assertIsNone(profile.block_1A)
        self.assertEqual(profile.block_2C_id, imported_course.id)
        self.assertIsNone(schedule["1A"]["course_id"])
        self.assertEqual(schedule["2C"]["course_id"], imported_course.id)

    def test_replacement_requires_all_nine_blocks_but_does_not_validate_course_blocks(self):
        old_course = self.make_course("Old Course", "1A")
        wrong_course = self.make_course("Wrong Block Course", "1A")
        profile = self.user.userprofile
        profile.block_1A = old_course
        profile.save()
        assignments = {block: None for block in USER_SCHEDULE_BLOCKS}
        assignments["2C"] = wrong_course.id

        incomplete_assignments = assignments.copy()
        incomplete_assignments.pop("1B")
        with self.assertRaisesMessage(ScheduleImportValidationError, "All nine blocks are required"):
            replace_user_schedule(profile, incomplete_assignments)

        profile.refresh_from_db()
        self.assertEqual(profile.block_1A_id, old_course.id)
        self.assertIsNone(profile.block_2C_id)

        replace_user_schedule(profile, assignments)
        profile.refresh_from_db()
        self.assertIsNone(profile.block_1A_id)
        self.assertEqual(profile.block_2C_id, wrong_course.id)

        with self.assertRaisesMessage(ScheduleImportValidationError, "Select at least one course"):
            replace_user_schedule(profile, {block: None for block in USER_SCHEDULE_BLOCKS})

    def test_web_course_form_uses_shared_replacement_without_block_validation(self):
        course = self.make_course("Database Blocks Pending", "1A")
        payload = {f"block_{block}": "NOCOURSE" for block in USER_SCHEDULE_BLOCKS}
        payload["block_2E"] = str(course.id)
        client = Client()
        client.login(school_email=self.user.school_email, password="password123")

        response = client.post(reverse("update_courses"), payload)

        self.assertEqual(response.status_code, 302)
        self.user.userprofile.refresh_from_db()
        self.assertEqual(self.user.userprofile.block_2E_id, course.id)


class ScheduleImportAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            school_email="schedule-api@wpga.ca",
            password="password123",
            first_name="API",
            last_name="Importer",
        )
        self.blocks = {code: Block.objects.create(code=code) for code in USER_SCHEDULE_BLOCKS}
        self.course = Course.objects.create(name="AP Calculus BC")
        self.course.blocks.add(self.blocks["2C"])

    @staticmethod
    def preview_payload():
        return {
            "blocks": [
                {
                    "block": block,
                    "extracted_name": "AP Calculus BC" if block == "2C" else None,
                    "course": None,
                    "suggestions": [],
                    "status": "needs_review" if block == "2C" else "missing",
                }
                for block in USER_SCHEDULE_BLOCKS
            ],
            "ignored": [],
            "summary": {"matched": 0, "unresolved": 1},
        }

    def authenticated_client(self):
        client = Client()
        client.login(school_email=self.user.school_email, password="password123")
        return client

    @patch("forum.api.schedule_import.build_schedule_preview")
    @patch("forum.api.schedule_import.extract_schedule_with_gemini")
    def test_text_preview_uses_authenticated_session(self, extract_mock, preview_mock):
        extract_mock.return_value = {"courses": [], "conflicts": {}, "ignored": []}
        preview_mock.return_value = self.preview_payload()

        response = self.authenticated_client().post(
            reverse("api_schedule_import_preview"),
            {"text": "AP Calculus BC - APCAL12A-2C (2C)"},
        )

        self.assertEqual(response.status_code, 200)
        extract_mock.assert_called_once_with(text="AP Calculus BC - APCAL12A-2C (2C)")
        self.assertEqual(len(response.json()["blocks"]), 9)

    @patch("forum.api.schedule_import.build_schedule_preview")
    @patch("forum.api.schedule_import.extract_schedule_with_gemini")
    def test_image_preview_accepts_token_authentication(self, extract_mock, preview_mock):
        extract_mock.return_value = {"courses": [], "conflicts": {}, "ignored": []}
        preview_mock.return_value = self.preview_payload()
        image_buffer = BytesIO()
        Image.new("RGB", (12, 12), "white").save(image_buffer, format="PNG")
        upload = SimpleUploadedFile("schedule.png", image_buffer.getvalue(), content_type="image/png")
        token = Token.objects.create(user=self.user)

        response = Client().post(
            reverse("api_schedule_import_preview"),
            {"image": upload},
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, 200)
        call_kwargs = extract_mock.call_args.kwargs
        self.assertEqual(call_kwargs["mime_type"], "image/png")
        self.assertTrue(call_kwargs["image_bytes"])

    def test_preview_rejects_anonymous_and_multiple_sources(self):
        anonymous = Client().post(reverse("api_schedule_import_preview"), {"text": "schedule"})
        self.assertIn(anonymous.status_code, (401, 403))

        both = self.authenticated_client().post(
            reverse("api_schedule_import_preview"),
            {
                "text": "schedule",
                "image": SimpleUploadedFile("schedule.png", b"not-an-image", content_type="image/png"),
            },
        )
        self.assertEqual(both.status_code, 422)

    @override_settings(SCHEDULE_IMPORT_RATE="1/hour")
    @patch("forum.api.schedule_import.build_schedule_preview")
    @patch("forum.api.schedule_import.extract_schedule_with_gemini")
    def test_preview_is_rate_limited_per_user(self, extract_mock, preview_mock):
        cache.clear()
        extract_mock.return_value = {"courses": [], "conflicts": {}, "ignored": []}
        preview_mock.return_value = self.preview_payload()
        client = self.authenticated_client()

        first = client.post(reverse("api_schedule_import_preview"), {"text": "schedule"})
        second = client.post(reverse("api_schedule_import_preview"), {"text": "schedule"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(extract_mock.call_count, 1)

    def test_apply_endpoint_replaces_all_nine_blocks(self):
        old_course = Course.objects.create(name="Old Course")
        old_course.blocks.add(self.blocks["1A"])
        self.user.userprofile.block_1A = old_course
        self.user.userprofile.save()
        assignments = {block: None for block in USER_SCHEDULE_BLOCKS}
        assignments["2C"] = self.course.id

        response = self.authenticated_client().post(
            reverse("api_schedule_import_apply"),
            data=json.dumps({"assignments": assignments}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.userprofile.refresh_from_db()
        self.assertIsNone(self.user.userprofile.block_1A)
        self.assertEqual(self.user.userprofile.block_2C_id, self.course.id)

    def test_session_apply_requires_csrf(self):
        assignments = {block: None for block in USER_SCHEDULE_BLOCKS}
        assignments["2C"] = self.course.id
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(school_email=self.user.school_email, password="password123")
        payload = json.dumps({"assignments": assignments})

        rejected = csrf_client.post(
            reverse("api_schedule_import_apply"),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 403)

        csrf_client.get(reverse("profile", kwargs={"username": self.user.username}))
        accepted = csrf_client.post(
            reverse("api_schedule_import_apply"),
            data=payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
        )
        self.assertEqual(accepted.status_code, 200)

    def test_profile_schedule_tab_contains_import_card_for_owner(self):
        client = self.authenticated_client()
        profile = client.get(reverse("profile", kwargs={"username": self.user.username}))
        self.assertContains(profile, 'id="profile-schedule-import-card"')
        self.assertContains(profile, 'id="profile-schedule-import-card" hidden')
        self.assertContains(profile, 'id="profile-schedule-import-toggle"')
        self.assertContains(profile, 'id="profile-import-image"')
        self.assertContains(profile, 'id="profile-import-text"')
        self.assertContains(profile, 'id="block_2C_selector"')

    def test_course_search_does_not_require_block_metadata(self):
        response = Client().get(reverse("course-search"), {"q": "AP Calculus BC"})

        self.assertEqual(response.status_code, 200)
        course = next(item for item in response.json() if item["id"] == self.course.id)
        self.assertNotIn("blocks", course)
