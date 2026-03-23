from django.test import TestCase, Client
from django.urls import reverse
from forum.models import User, Post, Course, Solution, Comment
from forum.services.utils import process_post_preview
import json

class GeneralURLTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpassword', school_email='test@wpga.ca', first_name='John', last_name='Doe')
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
        response = self.client.get(reverse('profile', kwargs={'username': 'testuser'}))
        self.assertEqual(response.status_code, 200)

    def test_compare_schedule_url(self):
        response = self.client.get(reverse('course_comparer'))
        self.assertEqual(response.status_code, 200)


class SolutionFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='soluser', password='solpass', school_email='sol@wpga.ca', first_name='John', last_name='Doe')
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
        self.user = User.objects.create_user(username='comuser', password='compass', school_email='com@wpga.ca', first_name='John', last_name='Doe')
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


class APIDeleteAccountTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', 
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
