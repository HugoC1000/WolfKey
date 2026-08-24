import json

from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token

from forum.models import Block, Course, User


class AtlasClassmateMatchingTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            school_email='viewer-atlas@wpga.ca',
            password='password123',
            first_name='Atlas',
            last_name='Viewer',
        )
        self.friend_one = User.objects.create_user(
            school_email='friend-one@wpga.ca',
            password='password123',
            first_name='Friend',
            last_name='One',
        )
        self.friend_two = User.objects.create_user(
            school_email='friend-two@wpga.ca',
            password='password123',
            first_name='Friend',
            last_name='Two',
        )
        self.block_1a = Block.objects.create(code='1A')
        self.block_1b = Block.objects.create(code='1B')
        self.shared_course = Course.objects.create(name='Shared Course')
        self.shared_course.blocks.add(self.block_1a, self.block_1b)

        self.friend_one.userprofile.block_1A = self.shared_course
        self.friend_one.userprofile.save()
        self.friend_two.userprofile.block_1B = self.shared_course
        self.friend_two.userprofile.save()

        self.client.login(school_email=self.viewer.school_email, password='password123')

    def generate(self):
        return self.client.post(
            reverse('session_generate_schedules'),
            data=json.dumps({
                'requested_course_ids': [self.shared_course.id],
                'required_course_ids': [self.shared_course.id],
            }),
            content_type='application/json',
        )

    def test_atlas_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse('timetable_assigner'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_disabled_viewer_sees_comparison_settings_message(self):
        self.viewer.userprofile.allow_schedule_comparison = False
        self.viewer.userprofile.save()

        response = self.client.get(reverse('timetable_assigner'))

        self.assertContains(response, 'You can’t compare schedules with friends')
        self.assertNotContains(response, 'id="user-selector-container"')
        self.assertContains(response, 'window.atlasClassmateMatchingEnabled = false;')

    def test_atlas_renders_inline_three_step_panels(self):
        response = self.client.get(reverse('timetable_assigner'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-atlas-panel="1"')
        self.assertContains(response, 'data-atlas-panel="2"')
        self.assertContains(response, 'data-atlas-panel="3"')
        self.assertContains(response, 'id="selectors-container"')
        self.assertContains(response, 'id="user-selector-container"')
        self.assertContains(response, 'id="evaluate-btn"')
        self.assertContains(response, 'id="atlas-results-step"')

    def test_block_course_reference_can_filter_by_maximum_taking_grade(self):
        self.viewer.userprofile.grade_level = 11
        self.viewer.userprofile.save()
        eligible_course = Course.objects.create(name='Grade 11 Eligible', category='Math', max_grade=12)
        eligible_course.blocks.add(self.block_1a)
        ineligible_course = Course.objects.create(name='Grade 10 Maximum', max_grade=10)
        ineligible_course.blocks.add(self.block_1a)

        filtered_response = self.client.get(
            reverse('session_all_courses_blocks'),
            {'eligible_only': '1'},
        )

        self.assertEqual(filtered_response.status_code, 200)
        filtered_courses = filtered_response.json()['blocks']['1A']
        self.assertIn(eligible_course.name, filtered_courses)
        self.assertNotIn(ineligible_course.name, filtered_courses)

        all_response = self.client.get(reverse('session_all_courses_blocks'))
        all_courses = all_response.json()['blocks']['1A']
        self.assertIn(eligible_course.name, all_courses)
        self.assertIn(ineligible_course.name, all_courses)
        course_links = all_response.json()['course_links']['1A']
        self.assertIn(
            {'id': eligible_course.id, 'name': eligible_course.name, 'url': reverse('course_page', args=[eligible_course.id]), 'color': '#E2C440', 'category_class': 'math'},
            course_links,
        )

        atlas_response = self.client.get(reverse('timetable_assigner'))
        self.assertContains(atlas_response, 'window.atlasHasGradeLevel = true;')

        token = Token.objects.create(user=self.viewer)
        mobile_response = self.client.get(
            reverse('api_all_courses_blocks'),
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        mobile_courses = mobile_response.json()['blocks']['1A']
        self.assertIn(eligible_course.name, mobile_courses)
        self.assertNotIn(ineligible_course.name, mobile_courses)

    def test_user_search_exposes_comparison_eligibility_only_when_requested(self):
        self.friend_two.userprofile.allow_schedule_comparison = False
        self.friend_two.userprofile.save()

        response = self.client.get(
            reverse('search_users_api'),
            {'query': 'Friend', 'limit': 10, 'include_schedule_comparison': '1'},
        )

        self.assertEqual(response.status_code, 200)
        users_by_id = {user['id']: user for user in response.json()['users']}
        self.assertTrue(users_by_id[self.friend_one.id]['schedule_comparison_enabled'])
        self.assertFalse(users_by_id[self.friend_two.id]['schedule_comparison_enabled'])

        default_response = self.client.get(
            reverse('search_users_api'),
            {'query': 'Friend', 'limit': 10},
        )
        for user in default_response.json()['users']:
            self.assertNotIn('schedule_comparison_enabled', user)

    def test_user_search_requires_authentication(self):
        self.client.logout()

        response = self.client.get(
            reverse('search_users_api'),
            {'query': 'Friend', 'include_schedule_comparison': '1'},
        )

        self.assertIn(response.status_code, (401, 403))

    def test_generation_keeps_classmate_matching_out_of_schedule_response(self):
        response = self.client.post(
            reverse('session_generate_schedules'),
            data=json.dumps({
                'requested_course_ids': [self.shared_course.id],
                'required_course_ids': [self.shared_course.id],
                'selected_user_ids': [self.friend_one.id],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        for schedule in response.json()['schedules']:
            for assignment in schedule['mapping'].values():
                self.assertNotIn('classmates', assignment)

    def test_generation_without_selected_people_keeps_existing_shape(self):
        response = self.generate()

        self.assertEqual(response.status_code, 200)
        for schedule in response.json()['schedules']:
            for assignment in schedule['mapping'].values():
                self.assertNotIn('classmates', assignment)

    def test_session_generation_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(
            school_email=self.viewer.school_email,
            password='password123',
        )
        payload = json.dumps({
            'requested_course_ids': [self.shared_course.id],
            'required_course_ids': [self.shared_course.id],
        })

        rejected = csrf_client.post(
            reverse('session_generate_schedules'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(rejected.status_code, 403)

        csrf_client.get(reverse('timetable_assigner'))
        csrf_token = csrf_client.cookies['csrftoken'].value
        accepted = csrf_client.post(
            reverse('session_generate_schedules'),
            data=payload,
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 200)

    def test_opted_in_person_schedule_is_available_for_local_matching(self):
        response = self.client.get(
            reverse('user_schedule_view', kwargs={'user_id': self.friend_one.id}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['schedule']['1A']['course_id'],
            self.shared_course.id,
        )

    def test_opted_out_person_schedule_is_rejected(self):
        self.friend_one.userprofile.allow_schedule_comparison = False
        self.friend_one.userprofile.save()

        response = self.client.get(
            reverse('user_schedule_view', kwargs={'user_id': self.friend_one.id}),
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn('schedule', response.json())

    def test_disabled_viewer_cannot_fetch_another_person_schedule(self):
        self.viewer.userprofile.allow_schedule_comparison = False
        self.viewer.userprofile.save()

        response = self.client.get(
            reverse('user_schedule_view', kwargs={'user_id': self.friend_one.id}),
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn('schedule', response.json())

    def test_mobile_generation_response_is_unchanged(self):
        token = Token.objects.create(user=self.viewer)

        response = self.client.post(
            reverse('api_generate_schedules'),
            data={
                'requested_course_ids': [self.shared_course.id],
                'required_course_ids': [self.shared_course.id],
            },
            format='json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(response.status_code, 200)
        for schedule in response.json()['schedules']:
            for assignment in schedule['mapping'].values():
                self.assertNotIn('classmates', assignment)
