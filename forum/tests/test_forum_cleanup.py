"""Regression coverage for shared forum rules used by web and API callers."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from forum.forms import CustomUserCreationForm, PostForm
from forum.models import Comment, CommentDownvote, CommentUpvote, Course, PollVote, Post, Solution, User
from forum.services.comment_services import vote_comment_service
from forum.services.post_list_service import prepare_posts
from forum.services.poll_services import cast_poll_vote
from forum.services.solution_services import create_solution_service
from forum.services.auth_services import register_user
from forum.services.auth_services import authenticate_user
from forum.services.post_services import update_post_service
from forum.services.profile_service import update_profile_info
from forum.services.community_services import get_owned_community_lunches
from forum.services.notification_services import mark_notification_read_service
from forum.services.utils import store_editor_image
from forum.serializers import PostListSerializer


class ForumCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'reviewer@wpga.ca', 'Review', 'User', password='test-password'
        )
        self.other = User.objects.create_user(
            'other-reviewer@wpga.ca', 'Other', 'User', password='test-password'
        )
        self.client.force_login(self.user)
        self.post = Post.objects.create(title='Discussion', content={}, author=self.user)
        self.solution = Solution.objects.create(post=self.post, author=self.user, content={})

    def test_profile_update_rejects_other_owner_before_any_writes(self):
        for data in (
            {'bio': 'Changed', 'first_name': 'Changed'},
            {'form_type': 'privacy_preferences', 'display_email': 'on'},
        ):
            with self.subTest(data=data):
                self.client.post(reverse('profile', args=[self.other.username]), data)
                self.other.userprofile.refresh_from_db()
                self.user.refresh_from_db()
                self.assertEqual(self.other.userprofile.bio, '')
                self.assertFalse(self.other.userprofile.display_email)
                self.assertEqual(self.user.first_name, 'Review')

    def test_web_profile_uses_serialized_privacy_rules(self):
        course = Course.objects.create(name='Private course')
        profile = self.other.userprofile
        profile.block_1A = course
        profile.allow_schedule_comparison = False
        profile.save()
        response = self.client.get(reverse('profile', args=[self.other.username]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.context['initial_courses_json']), {})
        self.assertFalse(response.context['can_compare'])
        self.assertIsNone(json.loads(response.context['initial_users']))

        profile.allow_schedule_comparison = True
        profile.save()
        response = self.client.get(reverse('profile', args=[self.other.username]))
        self.assertTrue(response.context['can_compare'])
        self.assertEqual(json.loads(response.context['initial_courses_json'])['1A']['course_id'], course.id)
        self.assertNotIn('school_email', response.context['initial_users'])

    def test_hidden_school_email_is_not_in_another_users_profile_html(self):
        response = self.client.get(reverse('profile', args=[self.other.username]))
        self.assertNotContains(response, self.other.school_email)

        self.other.userprofile.display_email = True
        self.other.userprofile.save(update_fields=['display_email'])
        response = self.client.get(reverse('profile', args=[self.other.username]))
        self.assertContains(response, self.other.school_email)

    def test_owner_can_reveal_email_without_reloading(self):
        response = self.client.get(reverse('profile', args=[self.user.username]))
        self.assertContains(response, self.user.school_email)
        self.assertContains(response, 'id="profileSchoolEmail"')

    def test_profile_api_handles_nullable_and_invalid_fields(self):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=self.user)
        headers = {'HTTP_AUTHORIZATION': f'Token {token.key}'}
        url = reverse('api_update_profile')
        self.user.userprofile.instagram_handle = 'reviewer'
        self.user.userprofile.save(update_fields=['instagram_handle'])

        response = self.client.post(
            url, data=json.dumps({'instagram_handle': None}),
            content_type='application/json', **headers,
        )
        self.assertEqual(response.status_code, 200)
        self.user.userprofile.refresh_from_db()
        self.assertIsNone(self.user.userprofile.instagram_handle)

        for data in (
            {'instagram_handle': {'value': 'bad'}},
            {'background_hue': None},
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    url, data=json.dumps(data), content_type='application/json', **headers,
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())

    def test_comment_parent_must_belong_to_same_solution(self):
        other_solution = Solution.objects.create(post=self.post, author=self.other, content={})
        parent = Comment.objects.create(solution=other_solution, author=self.other, content='Parent')
        response = self.client.post(
            reverse('create_comment', args=[self.solution.id]),
            data=json.dumps({'content': 'Reply', 'parent_id': parent.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Comment.objects.count(), 1)

    def test_comment_creation_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('create_comment', args=[self.solution.id]),
                                    data='{"content":"Reply"}', content_type='application/json')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.exists())

    def test_response_services_update_post_activity_explicitly(self):
        self.assertIsNone(self.post.last_activity_at)

        result = create_solution_service(
            self.other,
            self.post.id,
            {'content': {'blocks': [{'type': 'paragraph', 'data': {'text': 'Answer'}}]}},
        )
        self.assertNotIn('error', result)
        self.post.refresh_from_db()
        solution_activity = self.post.last_activity_at
        self.assertIsNotNone(solution_activity)

        response = self.client.post(
            reverse('create_comment', args=[result['id']]),
            data=json.dumps({
                'content': {'blocks': [{'type': 'paragraph', 'data': {'text': 'Follow-up'}}]},
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.post.refresh_from_db()
        self.assertGreaterEqual(self.post.last_activity_at, solution_activity)

    def test_poll_service_validates_options_from_the_same_poll(self):
        from forum.models import Poll, PollOption

        poll = Poll.objects.create(
            title='Choose one', content={}, author=self.user, post_type='poll'
        )
        valid_option = PollOption.objects.create(poll=poll, text='Valid')
        other_poll = Poll.objects.create(
            title='Other poll', content={}, author=self.user, post_type='poll'
        )
        other_option = PollOption.objects.create(poll=other_poll, text='Wrong poll')

        result = cast_poll_vote(self.other, poll.id, [valid_option.id])
        self.assertNotIn('error', result)

        result = cast_poll_vote(self.other, poll.id, [other_option.id])
        self.assertEqual(result['status'], 400)

    def test_editing_poll_vote_updates_timestamp(self):
        from datetime import timedelta
        from django.utils import timezone
        from forum.models import Poll, PollOption

        poll = Poll.objects.create(title='Choose one', content={}, author=self.user, post_type='poll')
        first = PollOption.objects.create(poll=poll, text='First')
        second = PollOption.objects.create(poll=poll, text='Second')
        cast_poll_vote(self.other, poll.id, [first.id])
        vote = PollVote.objects.get(poll=poll, user=self.other)
        old_time = timezone.now() - timedelta(days=1)
        PollVote.objects.filter(id=vote.id).update(updated_at=old_time)

        cast_poll_vote(self.other, poll.id, [second.id])
        vote.refresh_from_db()
        self.assertGreater(vote.updated_at, old_time)
        self.assertEqual(list(vote.selected_options.values_list('id', flat=True)), [second.id])

    def test_missing_comment_vote_uses_service_status_in_web_and_api(self):
        from rest_framework.authtoken.models import Token

        missing_id = 999999
        web_response = self.client.post(reverse('vote_comment', args=[missing_id, 'upvote']))
        self.assertEqual(web_response.status_code, 404)
        self.assertEqual(web_response.json(), {
            'success': False,
            'message': 'Comment not found',
            'data': None,
            'error_code': 'not_found',
        })

        token = Token.objects.create(user=self.user)
        api_response = self.client.post(
            reverse('api_vote_comment', args=[missing_id]),
            data=json.dumps({'vote_type': 'upvote'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertEqual(api_response.status_code, 404)
        self.assertEqual(api_response.json(), {'error': 'Comment not found'})

    def test_user_moderator_role_comes_from_profile(self):
        self.assertFalse(self.user.is_moderator)
        self.user.userprofile.is_moderator = True
        self.user.userprofile.save(update_fields=['is_moderator'])
        self.assertTrue(self.user.is_moderator)

    def test_registration_service_uses_validated_values_without_a_request(self):
        form = CustomUserCreationForm(data={
            'user_type': 'student',
            'first_name': 'Service',
            'last_name': 'Boundary',
            'school_email': 'service-boundary@wpga.ca',
            'personal_email': '',
            'grade_level': '11',
            'password1': 'BoundaryTest123!',
            'password2': 'BoundaryTest123!',
        })
        self.assertTrue(form.is_valid(), form.errors)

        result = register_user(
            form.cleaned_data,
            help_courses=[],
            experience_courses=[],
            allow_schedule_comparison=False,
        )

        self.assertNotIn('error', result)
        user = result['user']
        self.assertTrue(user.check_password('BoundaryTest123!'))
        self.assertEqual(user.userprofile.grade_level, 11)
        self.assertFalse(user.userprofile.allow_schedule_comparison)

    def test_shared_action_errors_have_message_and_status(self):
        cases = (
            (authenticate_user('missing@wpga.ca', 'wrong'), 401),
            (update_profile_info(self.user, self.other, {'bio': 'Changed'}), 403),
            (update_post_service(self.user, 999999, {'title': 'Changed'}), 404),
            (create_solution_service(self.user, 999999, {'content': 'Answer'}), 404),
            (cast_poll_vote(self.user, 999999, [1]), 404),
            (vote_comment_service(self.user, 999999, 'upvote'), 404),
            (get_owned_community_lunches(self.user), 403),
            (mark_notification_read_service(self.user, 999999), 404),
            (store_editor_image(None), 400),
        )
        for result, expected_status in cases:
            with self.subTest(result=result):
                self.assertEqual(set(result), {'error', 'status'})
                self.assertEqual(result['status'], expected_status)
                self.assertTrue(result['error'])

    def test_auth_entry_points_use_service_result(self):
        self.client.logout()
        web_login = self.client.post(
            reverse('login'),
            {'username': self.user.school_email, 'password': 'test-password'},
        )
        self.assertEqual(web_login.status_code, 302)

        login_response = self.client.post(
            reverse('api_login'),
            data=json.dumps({'school_email': self.user.school_email, 'password': 'test-password'}),
            content_type='application/json',
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('token', login_response.json())

        registration = {
            'user_type': 'student',
            'first_name': 'New',
            'last_name': 'Member',
            'school_email': 'new-member@wpga.ca',
            'personal_email': '',
            'grade_level': '10',
            'password1': 'BoundaryTest123!',
            'password2': 'BoundaryTest123!',
        }
        register_response = self.client.post(
            reverse('api_register'), data=json.dumps(registration), content_type='application/json'
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertEqual(register_response.json()['data']['user']['school_email'], registration['school_email'])

    def test_post_form_keeps_builtin_course_validation(self):
        course = Course.objects.create(name='Selected course')
        data = {'title': 'Title', 'content': '{"blocks":[]}', 'courses': [course.id]}
        form = PostForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(list(form.cleaned_data['courses']), [course])
        data['courses'] = [course.id + 1]
        self.assertFalse(PostForm(data).is_valid())

    def test_solution_file_cleanup_runs_once_via_delete_signal(self):
        from forum.services.solution_services import delete_solution_service
        self.solution.content = {'blocks': [{'type': 'image', 'data': {'file': {'url': '/media/test.png'}}}]}
        self.solution.save()
        with patch('forum.services.utils.extract_and_delete_files_from_content') as cleanup:
            result = delete_solution_service(self.user, self.solution.id)
        self.assertNotIn('error', result)
        cleanup.assert_called_once_with(self.solution.content)

    def test_comment_votes_are_exclusive_and_toggle(self):
        comment = Comment.objects.create(solution=self.solution, author=self.other, content='Useful')
        result = vote_comment_service(self.user, comment.id, 'upvote')
        self.assertEqual(result['vote_state'], 'upvoted')
        self.assertEqual(CommentUpvote.objects.count(), 1)
        result = vote_comment_service(self.user, comment.id, 'downvote')
        self.assertEqual(result['vote_state'], 'downvoted')
        self.assertFalse(CommentUpvote.objects.exists())
        self.assertEqual(CommentDownvote.objects.count(), 1)
        result = vote_comment_service(self.user, comment.id, 'downvote')
        self.assertEqual(result['vote_state'], 'none')
        self.assertFalse(CommentDownvote.objects.exists())

    def test_post_cards_keep_viewer_state_outside_the_post_model(self):
        course = Course.objects.create(name='Card course')
        self.post.courses.add(course)
        from forum.models import FollowedPost, PostLike
        PostLike.objects.create(post=self.post, user=self.user)
        FollowedPost.objects.create(post=self.post, user=self.user)

        item = prepare_posts(
            Post.objects.filter(id=self.post.id).select_related('author', 'author__userprofile').prefetch_related('courses'),
            self.user,
        )[0]

        self.assertEqual(item.post.id, self.post.id)
        self.assertTrue(item.is_liked)
        self.assertTrue(item.is_following)
        self.assertEqual(item.course_context[0]['name'], course.name)
        self.assertFalse(hasattr(item.post, 'is_liked_by_user'))
        self.assertEqual(PostListSerializer(item).data['like_count'], 1)
