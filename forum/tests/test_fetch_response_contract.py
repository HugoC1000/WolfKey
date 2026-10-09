import json

from django.test import TestCase
from django.urls import reverse

from forum.models import Comment, Course, Poll, PollOption, Post, Solution, User, UserCourseExperience


class CommentSolutionFetchResponseContractTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            password='contractpass',
            school_email='contract@wpga.ca',
            first_name='Contract',
            last_name='Tester',
        )
        self.course = Course.objects.create(name='Contract Test Course')
        self.post = Post.objects.create(title='Contract post', content='{}', author=self.user)
        self.solution = Solution.objects.create(
            post=self.post,
            author=self.user,
            content={'blocks': [{'type': 'paragraph', 'data': {'text': 'Answer'}}]},
        )
        self.comment = Comment.objects.create(
            solution=self.solution,
            author=self.user,
            content={'blocks': [{'type': 'paragraph', 'data': {'text': 'Comment'}}]},
        )
        self.client.login(school_email='contract@wpga.ca', password='contractpass')

    def assert_envelope(self, response, *, success, status_code):
        self.assertEqual(response.status_code, status_code)
        payload = response.json()
        self.assertEqual(set(payload), {'success', 'message', 'data', 'error_code'})
        self.assertIs(payload['success'], success)
        if success:
            self.assertIsNone(payload['error_code'])
        else:
            self.assertIsInstance(payload['error_code'], str)
            self.assertTrue(payload['error_code'])
            self.assertIsNone(payload['data'])
        return payload

    def test_comment_fetch_endpoints_use_envelope(self):
        response = self.client.get(
            reverse('get_solution_comments', args=[self.solution.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        data = self.assert_envelope(response, success=True, status_code=200)['data']
        self.assertEqual(len(data['comments']), 1)
        self.assertIn('html', data)

        response = self.client.post(
            reverse('create_comment', args=[self.solution.id]),
            data=json.dumps({'content': 'Created'}),
            content_type='application/json',
        )
        self.assert_envelope(response, success=True, status_code=201)

        response = self.client.post(
            reverse('edit_comment', args=[self.comment.id]),
            data=json.dumps({'content': 'Edited'}),
            content_type='application/json',
        )
        self.assert_envelope(response, success=True, status_code=200)

        response = self.client.post(
            reverse('vote_comment', args=[self.comment.id, 'upvote']),
        )
        vote_data = self.assert_envelope(response, success=True, status_code=200)['data']
        self.assertEqual(vote_data['vote_state'], 'upvoted')

        response = self.client.post(reverse('delete_comment', args=[self.comment.id]))
        self.assert_envelope(response, success=True, status_code=200)

    def test_solution_fetch_endpoints_use_envelope(self):
        response = self.client.post(
            reverse('edit_solution', args=[self.solution.id]),
            {'content': json.dumps({'blocks': [{'type': 'paragraph', 'data': {'text': 'Updated'}}]})},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assert_envelope(response, success=True, status_code=200)

        for name in ('upvote_solution', 'downvote_solution', 'accept_solution'):
            response = self.client.post(reverse(name, args=[self.solution.id]))
            self.assert_envelope(response, success=True, status_code=200)

        response = self.client.get(
            reverse('get_sorted_solutions', args=[self.post.id]),
        )
        data = self.assert_envelope(response, success=True, status_code=200)['data']
        self.assertEqual(len(data['solutions']), 1)

        response = self.client.post(reverse('delete_solution', args=[self.solution.id]))
        self.assert_envelope(response, success=True, status_code=200)

    def test_failures_use_envelope_and_matching_http_status(self):
        missing_id = self.comment.id + 10000
        response = self.client.post(reverse('delete_comment', args=[missing_id]))
        self.assert_envelope(response, success=False, status_code=404)

        response = self.client.post(reverse('accept_solution', args=[self.solution.id + 10000]))
        self.assert_envelope(response, success=False, status_code=404)

    def test_website_profile_fetch_endpoints_use_envelope(self):
        response = self.client.post(reverse('add_experience'), {'course': self.course.id})
        payload = self.assert_envelope(response, success=True, status_code=200)
        self.assertEqual(payload['message'], 'Course experience added successfully!')

        response = self.client.post(reverse('add_help_request'), {'course': self.course.id})
        self.assert_envelope(response, success=True, status_code=200)

        response = self.client.post(reverse('add_experience'), {'course': self.course.id})
        payload = self.assert_envelope(response, success=False, status_code=409)
        self.assertEqual(payload['error_code'], 'conflict')

        response = self.client.get(reverse('add_help_request'))
        self.assert_envelope(response, success=False, status_code=405)

    def test_post_actions_use_envelope(self):
        like = self.client.post(reverse('like_post', args=[self.post.id]))
        self.assertTrue(self.assert_envelope(like, success=True, status_code=200)['data']['liked'])

        follow = self.client.post(
            reverse('follow_post', args=[self.post.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertTrue(self.assert_envelope(follow, success=True, status_code=200)['data']['followed'])

        poll = Poll.objects.create(title='Choose one', content={}, author=self.user, post_type='poll')
        option = PollOption.objects.create(poll=poll, text='First')
        vote = self.client.post(
            reverse('vote_on_poll', args=[poll.id]),
            data=json.dumps({'selected_option_ids': [option.id]}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(self.assert_envelope(vote, success=True, status_code=200)['data']['user_vote']['selected_option_ids'], [option.id])

        remove = self.client.post(
            reverse('remove_poll_vote', args=[poll.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(self.assert_envelope(remove, success=True, status_code=200)['data']['poll_info']['total_votes'], 0)

    def test_mention_search_uses_envelope(self):
        response = self.client.get(reverse('mention_search'), {'query': ''})
        self.assertEqual(
            self.assert_envelope(response, success=True, status_code=200)['data'],
            {'users': [], 'courses': [], 'everyone': []},
        )

    def test_profile_settings_and_course_forms_support_fetch_envelopes(self):
        response = self.client.post(
            reverse('profile', args=[self.user.username]),
            {'first_name': 'Updated'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assert_envelope(response, success=True, status_code=200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')

        response = self.client.post(
            reverse('update_courses'),
            {'block_1A': self.course.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assert_envelope(response, success=True, status_code=200)
        self.user.userprofile.refresh_from_db()
        self.assertEqual(self.user.userprofile.block_1A_id, self.course.id)

        experience = UserCourseExperience.objects.create(user=self.user, course=self.course)
        response = self.client.post(
            reverse('remove_experience', args=[experience.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assert_envelope(response, success=True, status_code=200)

        response = self.client.post(
            reverse('upload_profile_picture'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assert_envelope(response, success=False, status_code=400)
