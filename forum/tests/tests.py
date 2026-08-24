from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.db.models import Count
from django.test import TestCase, Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from forum.models import (
    User, Post, Course, Solution, Comment, Notification,
    Block, CourseTeacher, FollowedPost, Poll, PollOption, PollVote, PostLike,
)
from forum.services.course_services import course_category_color
from forum.services.utils import process_post_preview
from forum.services.notification_services import all_notifications_service
from forum.serializers import (
    AnonymousAuthorSerializer,
    CommentSerializer,
    NotificationSerializer,
    PostDetailSerializer,
    PostListSerializer,
    PollSerializer,
    PrivateUserSerializer,
    SolutionSerializer,
    UserProfileSerializer,
    UserSummarySerializer,
)
from forum.serializers.user import safe_file_url
import json

class GeneralURLTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(password='testpassword', school_email='test@wpga.ca', first_name='John', last_name='Doe')
        self.course = Course.objects.create(name="Test Course")
        self.client.login(school_email='test@wpga.ca', password='testpassword')

    def test_for_you_url(self):
        response = self.client.get(reverse('for_you'))
        self.assertEqual(response.status_code, 200)

    def test_all_posts_url(self):
        response = self.client.get(reverse('all_posts'))
        self.assertEqual(response.status_code, 200)

    def test_create_post_url(self):
        response = self.client.get(reverse('create_post'))
        self.assertEqual(response.status_code, 200)

    def test_post_detail_url(self):
        post_data = {
            'title': 'Test Post',
            'content': json.dumps({'blocks': [{'type': 'paragraph', 'data': {'text': 'Test Content'}}]}),
            'courses': [self.course.id],
            'is_anonymous' : 'off',
        }
        response = self.client.post(reverse('create_post'), data=post_data)
        post = Post.objects.get(title='Test Post')

        response = self.client.get(reverse('post_detail', kwargs={'post_id': post.id}))
        self.assertEqual(response.status_code, 200)

    def test_register_url(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_login_url_get(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_logout_url(self):
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_search_posts_url(self):
        response = self.client.get(reverse('search_posts') + '?q=test_query')
        self.assertEqual(response.status_code, 200)

    def test_profile_view_url(self):
        response = self.client.get(reverse('profile', kwargs={'username': self.user.username}))
        self.assertEqual(response.status_code, 200)

    def test_compare_schedule_url(self):
        response = self.client.get(reverse('course_comparer'))
        self.assertEqual(response.status_code, 200)

    def test_all_posts_hides_non_teacher_visible_posts_for_anonymous_users(self):
        Post.objects.create(
            title='Hidden From Anonymous',
            content={'blocks': []},
            author=self.user,
            allow_teacher=True,
        )
        Post.objects.create(
            title='Visible To Anonymous',
            content={'blocks': []},
            author=self.user,
            allow_teacher=False,
        )

        self.client.logout()
        response = self.client.get(reverse('all_posts'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hidden From Anonymous')
        self.assertNotContains(response, 'Visible To Anonymous')

    def test_courses_use_their_category_hex_color(self):
        self.assertEqual(course_category_color('Math'), '#E2C440')
        self.assertNotEqual(course_category_color('Humanities'), course_category_color('Misc'))
        self.assertNotEqual(course_category_color('Study Hall'), course_category_color('Misc'))


class CoursePageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            password='coursepass', school_email='course@wpga.ca', first_name='Course', last_name='Member',
        )
        self.course = Course.objects.create(name='Physics 12', category='Science')
        self.block_1a = Block.objects.create(code='1A')
        self.block_2e = Block.objects.create(code='2E')
        self.course.blocks.add(self.block_1a, self.block_2e)
        self.user.userprofile.block_1A = self.course
        self.user.userprofile.save(update_fields=['block_1A'])
        self.post = Post.objects.create(title='Lab help', content={'blocks': []}, author=self.user)
        self.post.courses.add(self.course)
        self.client.login(school_email='course@wpga.ca', password='coursepass')

    def test_course_page_prompts_for_schedule_when_none_is_saved(self):
        self.user.userprofile.block_1A = None
        self.user.userprofile.save(update_fields=['block_1A'])

        response = self.client.get(reverse('course_page', kwargs={'course_id': self.course.id}))

        self.assertContains(response, 'Your schedule has not been uploaded yet.')
        self.assertNotContains(response, 'Students &amp; teachers by block')

    def test_course_page_prompts_to_enable_schedule_comparison(self):
        self.user.userprofile.allow_schedule_comparison = False
        self.user.userprofile.save(update_fields=['allow_schedule_comparison'])

        response = self.client.get(reverse('course_page', kwargs={'course_id': self.course.id}))

        self.assertContains(response, 'Schedule comparison is turned off.')
        self.assertNotContains(response, 'Students &amp; teachers by block')

    def test_course_page_shows_related_posts_and_block_grid(self):
        response = self.client.get(reverse('course_page', kwargs={'course_id': self.course.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Physics 12')
        self.assertContains(response, 'Lab help')
        self.assertContains(response, '1A')
        self.assertContains(response, '2E')
        self.assertNotContains(response, '1B')
        self.assertEqual(
            response.context['roster_blocks'],
            [
                {
                    'code': '1A',
                    'reports': [],
                    'can_contribute': True,
                    'students': [{
                        'username': self.user.username,
                        'full_name': 'Course Member',
                        'initials': 'CM',
                        'profile_picture_url': safe_file_url(self.user.userprofile.profile_picture),
                    }],
                },
                {
                    'code': '2E',
                    'reports': [],
                    'can_contribute': False,
                    'students': [],
                },
            ],
        )

    def test_add_teacher_report_without_creating_duplicates(self):
        response = self.client.post(
            reverse('contribute_course_teacher', kwargs={'course_id': self.course.id}),
            {'block': '1A', 'teacher_name': 'Ms. Rivera'},
        )
        self.assertRedirects(response, reverse('course_page', kwargs={'course_id': self.course.id}))
        report = CourseTeacher.objects.get(course=self.course, block='1A')
        self.assertEqual(report.teacher_name, 'Ms. Rivera')

        response = self.client.post(
            reverse('contribute_course_teacher', kwargs={'course_id': self.course.id}),
            {'block': '1A', 'teacher_name': 'Ms. Rivera'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CourseTeacher.objects.filter(course=self.course, block='1A').count(), 1)

    def test_course_page_renders_teacher_edit_control(self):
        report = CourseTeacher.objects.create(
            course=self.course,
            block='1A',
            teacher_name="Ms. O'Connor",
        )

        response = self.client.get(reverse('course_page', kwargs={'course_id': self.course.id}))

        self.assertContains(
            response,
            reverse('edit_course_teacher', kwargs={
                'course_id': self.course.id,
                'report_id': report.id,
            }),
        )
        self.assertContains(response, 'data-teacher-name="Ms. O&#x27;Connor"')
        self.assertNotContains(response, 'endorse-button')

    def test_non_class_member_cannot_change_teacher_information(self):
        outsider = User.objects.create_user(
            password='outsiderpass',
            school_email='outsider@wpga.ca',
            first_name='Outside',
            last_name='Member',
        )
        other_course = Course.objects.create(name='Other Course')
        outsider.userprofile.block_1A = other_course
        outsider.userprofile.save(update_fields=['block_1A'])
        self.client.login(school_email='outsider@wpga.ca', password='outsiderpass')

        add_response = self.client.post(
            reverse('contribute_course_teacher', kwargs={'course_id': self.course.id}),
            {'block': '1A', 'teacher_name': 'Ms. Rivera'},
        )
        self.assertEqual(add_response.status_code, 403)

        report = CourseTeacher.objects.create(
            course=self.course,
            block='1A',
            teacher_name='Ms. Rivera',
        )
        edit_response = self.client.post(
            reverse('edit_course_teacher', kwargs={
                'course_id': self.course.id,
                'report_id': report.id,
            }),
            {'teacher_name': 'Changed Name'},
        )

        self.assertEqual(edit_response.status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.teacher_name, 'Ms. Rivera')

    def test_teacher_name_can_be_corrected_without_losing_the_report(self):
        report = CourseTeacher.objects.create(course=self.course, block='1A', teacher_name='Ms River')
        response = self.client.post(
            reverse('edit_course_teacher', kwargs={'course_id': self.course.id, 'report_id': report.id}),
            {'teacher_name': 'Ms. Rivera'},
        )
        self.assertRedirects(response, reverse('course_page', kwargs={'course_id': self.course.id}))
        report.refresh_from_db()
        self.assertEqual(report.teacher_name, 'Ms. Rivera')


class SolutionFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(password='solpass', school_email='sol@wpga.ca', first_name='John', last_name='Doe')
        self.course = Course.objects.create(name="Test Course")
        self.post = Post.objects.create(title='Test Post', content='{}', author=self.user)
        self.client.login(school_email='sol@wpga.ca', password='solpass')

    def test_create_solution(self):
        url = reverse('create_solution', kwargs={'post_id': self.post.id})
        data = {
            'content': json.dumps({'blocks': [{'type': 'paragraph', 'data': {'text': 'Solution content'}}]})
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Solution.objects.filter(post=self.post).exists())

    def test_edit_solution(self):
        solution = Solution.objects.create(post=self.post, author=self.user, content={'blocks': []})
        url = reverse('edit_solution', kwargs={'solution_id': solution.id})
        data = {
            'content': json.dumps({'blocks': [{'type': 'paragraph', 'data': {'text': 'Edited content'}}]})
        }
        response = self.client.post(url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        solution.refresh_from_db()
        self.assertIn('Edited content', json.dumps(solution.content))

    def test_delete_solution(self):
        solution = Solution.objects.create(post=self.post, author=self.user, content={'blocks': []})
        url = reverse('delete_solution', kwargs={'solution_id': solution.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Solution.objects.filter(id=solution.id).exists())

    def test_upvote_solution(self):
        solution = Solution.objects.create(post=self.post, author=self.user, content={'blocks': []})
        url = reverse('upvote_solution', kwargs={'solution_id': solution.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('upvotes', response.json())

    def test_downvote_solution(self):
        solution = Solution.objects.create(post=self.post, author=self.user, content={'blocks': []})
        url = reverse('downvote_solution', kwargs={'solution_id': solution.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('downvotes', response.json())

    def test_accept_solution(self):
        solution = Solution.objects.create(post=self.post, author=self.user, content={'blocks': []})
        url = reverse('accept_solution', kwargs={'solution_id': solution.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('is_accepted', response.json())


class CommentFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(password='compass', school_email='com@wpga.ca', first_name='John', last_name='Doe')
        self.course = Course.objects.create(name="Test Course")
        self.post = Post.objects.create(title='Test Post', content='{}', author=self.user)
        self.solution = Solution.objects.create(post=self.post, author=self.user, content={'blocks': []})
        self.client.login(school_email='com@wpga.ca', password='compass')

    def test_create_comment(self):
        url = reverse('create_comment', kwargs={'solution_id': self.solution.id})
        data = {'content': 'Test comment'}
        response = self.client.post(url, data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Comment.objects.filter(solution=self.solution).exists())

    def test_edit_comment(self):
        comment = Comment.objects.create(solution=self.solution, author=self.user, content='Old comment')
        url = reverse('edit_comment', kwargs={'comment_id': comment.id})
        data = {'content': 'Edited comment'}
        response = self.client.post(url, data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.content, 'Edited comment')

    def test_delete_comment(self):
        comment = Comment.objects.create(solution=self.solution, author=self.user, content='To delete')
        url = reverse('delete_comment', kwargs={'comment_id': comment.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(id=comment.id).exists())


class AnonymousSerializationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            password='authorpass',
            school_email='anonymous-author@wpga.ca',
            personal_email='private@example.com',
            phone_number='555-0199',
            student_id='987654',
            first_name='Secret',
            last_name='Person',
        )
        self.other = User.objects.create_user(
            password='otherpass',
            school_email='other-author@wpga.ca',
            first_name='Public',
            last_name='Person',
        )
        self.post = Post.objects.create(
            title='Anonymous post',
            content={'blocks': []},
            author=self.author,
            is_anonymous=True,
        )
        self.author_solution = Solution.objects.create(
            post=self.post,
            author=self.author,
            content={'blocks': []},
        )
        self.other_solution = Solution.objects.create(
            post=self.post,
            author=self.other,
            content={'blocks': []},
        )
        self.author_comment = Comment.objects.create(
            solution=self.other_solution,
            author=self.author,
            content={'blocks': []},
        )

    def assertAnonymousAuthor(self, author):
        self.assertIsNone(author['id'])
        self.assertEqual(author['username'], '')
        self.assertEqual(author['full_name'], 'Anonymous')
        self.assertTrue(author['is_anonymous'])
        serialized = json.dumps(author)
        self.assertNotIn(self.author.school_email, serialized)
        self.assertNotIn(self.author.personal_email, serialized)
        self.assertNotIn(self.author.phone_number, serialized)
        self.assertNotIn(self.author.student_id, serialized)

    def test_anonymous_author_projection_contains_only_safe_identity_data(self):
        data = AnonymousAuthorSerializer(self.author).data

        self.assertAnonymousAuthor(data)
        self.assertEqual(
            set(data),
            {
                'id', 'username', 'first_name', 'last_name', 'full_name',
                'profile_picture_url', 'userprofile', 'grade_level',
                'is_teacher', 'is_anonymous',
            },
        )

    def test_post_list_and_detail_use_anonymous_author_projection(self):
        self.assertAnonymousAuthor(PostListSerializer(self.post).data['author'])
        self.assertAnonymousAuthor(PostDetailSerializer(self.post).data['author'])

    def test_solution_derives_anonymity_without_serializer_context(self):
        anonymous_data = SolutionSerializer(self.author_solution).data
        public_data = SolutionSerializer(self.other_solution).data

        self.assertAnonymousAuthor(anonymous_data['author'])
        self.assertIn('mentions', anonymous_data)
        self.assertEqual(public_data['author']['id'], self.other.id)

    def test_comment_derives_anonymity_without_serializer_context(self):
        data = CommentSerializer(self.author_comment).data

        self.assertAnonymousAuthor(data['author'])
        self.assertIn('mentions', data)

    def test_notification_uses_anonymous_sender_projection(self):
        from rest_framework.authtoken.models import Token

        notification = Notification.objects.create(
            recipient=self.other,
            sender=self.author,
            notification_type='comment',
            post=self.post,
            comment=self.author_comment,
            message='Anonymous commented.',
        )

        data = NotificationSerializer(notification).data

        self.assertAnonymousAuthor(data['sender'])

        token = Token.objects.create(user=self.other)
        response = self.client.get(
            reverse('api_notifications'),
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(response.status_code, 200)
        api_sender = response.json()['data']['notifications'][0]['sender']
        self.assertAnonymousAuthor(api_sender)

    def test_notification_resolves_post_through_solution_without_extra_queries(self):
        notification = Notification.objects.create(
            recipient=self.other,
            sender=self.author,
            notification_type='solution',
            solution=self.author_solution,
            message='Anonymous answered.',
        )
        notifications = list(all_notifications_service(self.other))

        with CaptureQueriesContext(connection) as queries:
            data = NotificationSerializer(notifications, many=True).data

        self.assertEqual(len(queries), 0)
        self.assertEqual(data[0]['id'], notification.id)
        self.assertEqual(data[0]['post_title'], self.post.title)
        self.assertAnonymousAuthor(data[0]['sender'])

    def test_legacy_sorted_solutions_endpoint_uses_safe_author_projection(self):
        response = self.client.get(
            reverse('get_sorted_solutions', kwargs={'post_id': self.post.id})
        )

        self.assertEqual(response.status_code, 200)
        solutions = {
            solution['id']: solution for solution in response.json()['solutions']
        }
        self.assertAnonymousAuthor(solutions[self.author_solution.id]['author'])
        self.assertEqual(solutions[self.other_solution.id]['author']['id'], self.other.id)

    def test_legacy_comments_endpoint_uses_safe_author_projection(self):
        response = self.client.get(
            reverse(
                'get_solution_comments',
                kwargs={'solution_id': self.other_solution.id},
            ),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertAnonymousAuthor(response.json()['comments'][0]['author'])
        self.assertNotContains(response, self.author.get_full_name())


class SerializerRefactorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = User.objects.create_user(
            password='ownerpass',
            school_email='owner@wpga.ca',
            first_name='Owner',
            last_name='User',
        )
        self.viewer = User.objects.create_user(
            password='viewerpass',
            school_email='viewer-summary@wpga.ca',
            first_name='Viewer',
            last_name='User',
        )
        self.course = Course.objects.create(name='Private Schedule Course')
        self.owner.userprofile.block_1A = self.course
        self.owner.userprofile.allow_schedule_comparison = False
        self.owner.userprofile.preferred_msg_app = 'LinkedIn'
        self.owner.userprofile.instagram_handle = 'owner.user'
        self.owner.userprofile.snapchat_handle = 'owner-snap'
        self.owner.userprofile.linkedin_url = 'https://www.linkedin.com/in/owner-user'
        self.owner.userprofile.save()
        self.post = Post.objects.create(
            title='Serializer test post',
            content={'blocks': []},
            author=self.owner,
        )

    def test_public_profile_schedule_defaults_to_hidden(self):
        request = self.factory.get('/')
        request.user = AnonymousUser()

        data = UserProfileSerializer(
            self.owner.userprofile,
            context={'request': request},
        ).data

        self.assertIsNone(data['schedule'])
        self.assertNotIn('block_1A', data)
        self.assertNotIn('schedule_blocks', data)
        self.assertNotIn('schedule_courses', data['courses'])

    def test_private_profile_can_include_owner_schedule_without_request_context(self):
        data = PrivateUserSerializer(self.owner).data

        self.assertEqual(
            data['userprofile']['schedule']['1A']['course_id'],
            self.course.id,
        )

    def test_user_summary_embeds_only_compact_contact_profile(self):
        data = UserSummarySerializer(self.owner).data

        self.assertNotIn('date_joined', data)
        self.assertEqual(data['id'], self.owner.id)
        self.assertEqual(
            data['userprofile'],
            {
                'profile_picture': self.owner.userprofile.profile_picture.url,
                'preferred_msg_app': 'LinkedIn',
                'instagram_url': 'https://www.instagram.com/owner.user',
                'snapchat_url': 'https://www.snapchat.com/add/owner-snap',
                'linkedin_url': 'https://www.linkedin.com/in/owner-user',
            },
        )

    def test_post_summary_and_detail_include_author_preferred_message_app(self):
        summary = PostListSerializer(self.post).data
        detail = PostDetailSerializer(self.post).data

        expected_profile_fields = {
            'preferred_msg_app': 'LinkedIn',
            'instagram_url': 'https://www.instagram.com/owner.user',
            'snapchat_url': 'https://www.snapchat.com/add/owner-snap',
            'linkedin_url': 'https://www.linkedin.com/in/owner-user',
        }
        for payload in (summary, detail):
            with self.subTest(serializer_payload=payload['id']):
                author_profile = payload['author']['userprofile']
                for field, expected_value in expected_profile_fields.items():
                    self.assertEqual(author_profile[field], expected_value)

    def test_solution_serializes_only_root_comments_at_top_level(self):
        solution = Solution.objects.create(
            post=self.post,
            author=self.viewer,
            content={'blocks': []},
        )
        root = Comment.objects.create(
            solution=solution,
            author=self.viewer,
            content={'blocks': []},
        )
        reply = Comment.objects.create(
            solution=solution,
            author=self.owner,
            parent=root,
            content={'blocks': []},
        )

        comments = SolutionSerializer(solution).data['comments']

        self.assertEqual([comment['id'] for comment in comments], [root.id])
        self.assertEqual(
            [comment['id'] for comment in comments[0]['replies']],
            [reply.id],
        )

    def test_annotated_solution_count_does_not_run_fallback_query(self):
        annotated_post = Post.objects.annotate(
            solution_count=Count('solutions')
        ).get(id=self.post.id)
        serializer = PostListSerializer()

        with CaptureQueriesContext(connection) as queries:
            solution_count = serializer.get_solution_count(annotated_post)

        self.assertEqual(solution_count, 0)
        self.assertEqual(len(queries), 0)

    def test_post_card_engagement_falls_back_when_annotations_are_missing(self):
        PostLike.objects.create(post=self.post, user=self.viewer)
        FollowedPost.objects.create(post=self.post, user=self.viewer)
        request = self.factory.get('/')
        request.user = self.viewer
        serializer = PostListSerializer(context={'request': request})

        self.assertTrue(serializer.get_is_liked(self.post))
        self.assertTrue(serializer.get_is_following(self.post))

    def test_poll_state_is_computed_once_without_per_option_queries(self):
        poll = Poll.objects.create(
            title='Efficient poll',
            content={'blocks': []},
            author=self.owner,
            is_public_voting=True,
            allow_multiple_choice=False,
        )
        first = PollOption.objects.create(poll=poll, text='First')
        second = PollOption.objects.create(poll=poll, text='Second')
        owner_vote = PollVote.objects.create(poll=poll, user=self.owner)
        owner_vote.selected_options.add(first)
        viewer_vote = PollVote.objects.create(poll=poll, user=self.viewer)
        viewer_vote.selected_options.add(second)
        request = self.factory.get('/')
        request.user = self.viewer

        with CaptureQueriesContext(connection) as queries:
            data = PollSerializer(poll, context={'request': request}).data

        self.assertLessEqual(len(queries), 5)
        options = {option['id']: option for option in data['poll_options']}
        self.assertEqual(data['poll_info']['total_votes'], 2)
        self.assertEqual(options[first.id]['vote_count'], 1)
        self.assertEqual(options[second.id]['vote_count'], 1)
        self.assertFalse(options[first.id]['user_voted'])
        self.assertTrue(options[second.id]['user_voted'])
        self.assertEqual(data['user_vote']['selected_option_ids'], [second.id])
        self.assertEqual(len(options[first.id]['voters']), 1)


class APIDeleteAccountTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            password='testpassword123', 
            school_email='test@wpga.ca', 
            first_name='John', 
            last_name='Doe'
        )
        # Create an API token for the user
        from rest_framework.authtoken.models import Token
        self.token = Token.objects.create(user=self.user)
        
    def test_delete_account_success(self):
        """Test successful account deletion with valid token"""
        url = reverse('api_delete_account')
        response = self.client.delete(
            url,
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('message', response_data['data'])
        
        # Verify user is deleted
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        
    def test_delete_account_with_password_confirmation(self):
        """Test account deletion with password confirmation"""
        url = reverse('api_delete_account')
        data = {'password': 'testpassword123'}
        
        response = self.client.delete(
            url,
            data=json.dumps(data),
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verify user is deleted
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        
    def test_delete_account_wrong_password(self):
        """Test account deletion with wrong password"""
        url = reverse('api_delete_account')
        data = {'password': 'wrongpassword'}
        
        response = self.client.delete(
            url,
            data=json.dumps(data),
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error']['code'], 'INVALID_PASSWORD')
        
        # Verify user is NOT deleted
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_delete_account_no_auth(self):
        """Test account deletion without authentication"""
        url = reverse('api_delete_account')
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, 401)
        
        # Verify user is NOT deleted
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_delete_account_invalid_token(self):
        """Test account deletion with invalid token"""
        url = reverse('api_delete_account')
        response = self.client.delete(
            url,
            HTTP_AUTHORIZATION='Token invalidtoken123',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
        
        # Verify user is NOT deleted
        self.assertTrue(User.objects.filter(id=self.user.id).exists())


class MentionAutocompleteAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='mentionuser',
            password='mentionpass',
            school_email='mention@wpga.ca',
            first_name='Mia',
            last_name='Jones'
        )
        self.teacher = User.objects.create_user(
            username='teachuser',
            password='teachpass',
            school_email='teach@wpga.ca',
            first_name='Tara',
            last_name='Smith',
            is_teacher=True
        )
        self.course = Course.objects.create(name='Biology', category='Science')

    def test_mentions_users_autocomplete_returns_users(self):
        self.client.login(school_email='mention@wpga.ca', password='mentionpass')

        response = self.client.get(reverse('mentions_users_autocomplete_api') + '?query=mi&limit=5')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('users', payload)
        self.assertTrue(any(user['username'] == 'mentionuser' for user in payload['users']))

    def test_mentions_courses_autocomplete_returns_courses(self):
        self.client.login(school_email='mention@wpga.ca', password='mentionpass')

        response = self.client.get(reverse('mentions_courses_autocomplete_api') + '?query=bio&limit=5')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('courses', payload)
        self.assertTrue(any(course['name'] == 'Biology' for course in payload['courses']))

    def test_mentions_autocomplete_includes_everyone_for_teacher(self):
        self.client.login(school_email='teach@wpga.ca', password='teachpass')

        response = self.client.get(reverse('mentions_users_autocomplete_api') + '?query=eve')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['everyone'][0]['name'], 'everyone')

    def test_mentions_autocomplete_hides_everyone_for_non_teacher(self):
        self.client.login(school_email='mention@wpga.ca', password='mentionpass')

        response = self.client.get(reverse('mentions_users_autocomplete_api') + '?query=eve')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['everyone'], [])


class APIProfilePostsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.viewer = User.objects.create_user(
            password='viewerpass123',
            school_email='viewer@wpga.ca',
            first_name='View',
            last_name='Er'
        )
        self.qa_user = User.objects.create_user(
            password='qapass123',
            school_email='qa@wpga.ca',
            first_name='QA',
            last_name='User',
            is_teacher=True
        )
        self.other_user = User.objects.create_user(
            password='otherpass123',
            school_email='other@wpga.ca',
            first_name='Other',
            last_name='User'
        )

        from rest_framework.authtoken.models import Token
        self.token = Token.objects.create(user=self.viewer)

        Post.objects.create(
            title='QA Visible Old',
            content={'blocks': []},
            author=self.qa_user,
            is_anonymous=False
        )
        Post.objects.create(
            title='QA Visible New',
            content={'blocks': []},
            author=self.qa_user,
            is_anonymous=False
        )
        Post.objects.create(
            title='QA Anonymous Hidden',
            content={'blocks': []},
            author=self.qa_user,
            is_anonymous=True
        )
        Post.objects.create(
            title='Other User Post',
            content={'blocks': []},
            author=self.other_user,
            is_anonymous=False
        )

    def test_get_profile_posts_api_returns_only_public_posts_for_requested_user(self):
        url = reverse('api_get_profile_posts', kwargs={'username': self.qa_user.username})
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload['username'], self.qa_user.username)
        self.assertTrue(payload['is_qa_user'])

        titles = [post['title'] for post in payload['posts']]
        self.assertIn('QA Visible Old', titles)
        self.assertIn('QA Visible New', titles)
        self.assertNotIn('QA Anonymous Hidden', titles)
        self.assertNotIn('Other User Post', titles)

    def test_get_profile_posts_api_supports_pagination(self):
        url = reverse('api_get_profile_posts', kwargs={'username': self.qa_user.username})
        response = self.client.get(f'{url}?limit=1', HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(len(payload['posts']), 1)
        self.assertEqual(payload['posts'][0]['title'], 'QA Visible New')
        self.assertTrue(payload['has_next'])
        self.assertEqual(payload['total_pages'], 2)


class APIProfilePrivacyTests(TestCase):
    def setUp(self):
        from rest_framework.authtoken.models import Token

        self.client = Client()
        self.viewer = User.objects.create_user(
            password='viewerpass123', school_email='viewer@wpga.ca',
            personal_email='viewer@example.com', first_name='View', last_name='Er'
        )
        self.other = User.objects.create_user(
            password='otherpass123', school_email='other@wpga.ca',
            personal_email='other@example.com', phone_number='555-0100',
            student_id='123456', first_name='Other', last_name='User'
        )
        self.other.userprofile.wolfnet_password = 'secret'
        self.other.userprofile.lunch_card = 'lunch_cards/private.png'
        self.other.userprofile.display_email = False
        self.other.userprofile.allow_schedule_comparison = False
        self.other.userprofile.save()
        self.token = Token.objects.create(user=self.viewer)

    def _get_profile(self, user):
        return self.client.get(
            reverse('api_get_profile', kwargs={'username': user.username}),
            HTTP_AUTHORIZATION=f'Token {self.token.key}'
        )

    def test_other_users_profile_only_returns_public_fields(self):
        response = self._get_profile(self.other)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn('personal_email', payload)
        self.assertNotIn('phone_number', payload)
        self.assertNotIn('student_id', payload)
        self.assertIsNone(payload['school_email'])
        self.assertNotIn('lunch_card', payload['userprofile'])
        self.assertNotIn('has_wolfnet_password', payload['userprofile'])
        self.assertNotIn('display_email', payload['userprofile'])
        self.assertIsNone(payload['userprofile']['schedule'])
        self.assertNotIn('schedule_courses', payload['userprofile']['courses'])
        self.assertFalse(payload['userprofile']['can_compare'])

    def test_own_profile_returns_owner_only_fields(self):
        response = self._get_profile(self.viewer)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['school_email'], self.viewer.school_email)
        self.assertIn('personal_email', payload)
        self.assertIn('phone_number', payload)
        self.assertIn('student_id', payload)
        self.assertIn('lunch_card', payload['userprofile'])
        self.assertIn('display_email', payload['userprofile'])


class PreferredMessageAppTests(TestCase):
    def setUp(self):
        from rest_framework.authtoken.models import Token

        self.client = Client()
        self.user = User.objects.create_user(
            password='profilepass123', school_email='profile@wpga.ca',
            first_name='Profile', last_name='User'
        )
        self.token = Token.objects.create(user=self.user)
        self.auth_header = {'HTTP_AUTHORIZATION': f'Token {self.token.key}'}

    def test_profile_api_updates_and_returns_preferred_message_app(self):
        for app in ('Instagram', 'LinkedIn', 'Snapchat', 'Email', 'Discord'):
            with self.subTest(app=app):
                response = self.client.post(
                    reverse('api_update_profile'),
                    data=json.dumps({'preferred_msg_app': app}),
                    content_type='application/json',
                    **self.auth_header,
                )
                self.assertEqual(response.status_code, 200)
                self.user.userprofile.refresh_from_db()
                self.assertEqual(self.user.userprofile.preferred_msg_app, app)

        self.user.userprofile.refresh_from_db()
        self.assertEqual(self.user.userprofile.preferred_msg_app, 'Discord')

        response = self.client.get(reverse('api_get_current_profile'), **self.auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['userprofile']['preferred_msg_app'], 'Discord')

        response = self.client.post(
            reverse('api_update_profile'),
            data=json.dumps({'preferred_msg_app': None}),
            content_type='application/json',
            **self.auth_header,
        )
        self.assertEqual(response.status_code, 200)
        self.user.userprofile.refresh_from_db()
        self.assertIsNone(self.user.userprofile.preferred_msg_app)

    def test_profile_api_rejects_unknown_preferred_message_app(self):
        response = self.client.post(
            reverse('api_update_profile'),
            data=json.dumps({'preferred_msg_app': 'sms'}),
            content_type='application/json',
            **self.auth_header,
        )

        self.assertEqual(response.status_code, 400)
        self.user.userprofile.refresh_from_db()
        self.assertIsNone(self.user.userprofile.preferred_msg_app)

    def test_profile_page_has_preferred_message_app_selector(self):
        self.user.userprofile.preferred_msg_app = 'Snapchat'
        self.user.userprofile.save()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('profile', kwargs={'username': self.user.username})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="preferred_msg_app"')
        self.assertContains(response, '<option value="Snapchat" selected>Snapchat</option>', html=True)
        content = response.content.decode()
        self.assertGreater(
            content.index('id="socialMediaForm"'),
            content.index('id="preferences"'),
        )


class PostPreviewFormattingTests(TestCase):
    def _build_post(self, content):
        return type('PostStub', (), {'content': content})()

    def test_post_preview_supports_multiple_block_types(self):
        content = {
            'blocks': [
                {'type': 'header', 'data': {'text': 'Main Heading'}},
                {'type': 'paragraph', 'data': {'text': 'Paragraph line 1<br>Paragraph line 2'}},
                {'type': 'list', 'data': {'items': ['First bullet', 'Second bullet']}},
                {'type': 'checklist', 'data': {'items': [{'text': 'Checked item', 'checked': True}]}},
                {'type': 'quote', 'data': {'text': 'Quoted text', 'caption': 'Speaker'}},
                {'type': 'code', 'data': {'code': 'x = 1'}},
                {'type': 'table', 'data': {'content': [['A', 'B'], ['1', '2']]}},
                {'type': 'warning', 'data': {'title': 'Heads up', 'message': 'Be careful'}},
                {'type': 'image', 'data': {'caption': 'Figure caption'}},
                {'type': 'math', 'data': {'math': 'x^2 + y^2'}},
            ]
        }

        preview = process_post_preview(self._build_post(content))

        self.assertIn('Main Heading', preview)
        self.assertIn('Paragraph line 1\nParagraph line 2', preview)
        self.assertIn('First bullet', preview)
        self.assertIn('Checked item', preview)
        self.assertIn('Quoted text\nSpeaker', preview)
        self.assertIn('x = 1', preview)
        self.assertIn('A | B', preview)
        self.assertIn('Heads up\nBe careful', preview)
        self.assertIn('Figure caption', preview)
        self.assertIn('x^2 + y^2', preview)

    def test_post_preview_preserves_newlines_from_inline_breaks(self):
        content = {
            'blocks': [
                {'type': 'paragraph', 'data': {'text': 'Line one<br>Line two<br/>Line three'}}
            ]
        }

        preview = process_post_preview(self._build_post(content))

        self.assertEqual(preview, 'Line one\nLine two\nLine three')

    def test_post_preview_parses_json_string_content(self):
        content = json.dumps({
            'blocks': [
                {'type': 'paragraph', 'data': {'text': 'From JSON string'}}
            ]
        })

        preview = process_post_preview(self._build_post(content))

        self.assertEqual(preview, 'From JSON string')

    def test_post_preview_returns_empty_string_when_no_text(self):
        content = {
            'blocks': [
                {'type': 'delimiter', 'data': {}},
                {'type': 'image', 'data': {'caption': ''}},
            ]
        }

        preview = process_post_preview(self._build_post(content))

        self.assertEqual(preview, '')
