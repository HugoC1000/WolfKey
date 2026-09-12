"""Regression coverage for shared forum rules used by web and API callers."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from forum.forms import PostForm
from forum.models import Comment, CommentDownvote, CommentUpvote, Course, Post, Solution, User
from forum.services.comment_services import vote_comment_service
from forum.services.post_list_service import prepare_posts
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
            {'form_type': 'wolfnet_settings', 'clear_wolfnet_password': 'true'},
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
