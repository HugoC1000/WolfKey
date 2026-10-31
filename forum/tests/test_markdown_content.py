from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.apps import apps
from django.db import connection
from django.db.models import F
from django.contrib.postgres.search import SearchQuery, SearchRank
from rest_framework.test import APIClient
from unittest.mock import patch
from types import SimpleNamespace

from forum.models import Comment, Post, Solution, User
from forum.services.content_format import (
    editorjs_to_markdown, markdown_image_urls, markdown_plain_text,
    markdown_to_editorjs, render_markdown, set_content_representations,
)
from forum.services.mention_service import parse_editorjs_text_mentions


class MarkdownConversionTests(SimpleTestCase):
    def test_supported_blocks_round_trip_without_changing_legacy_source(self):
        legacy = {'blocks': [
            {'type': 'header', 'data': {'text': 'Hello <b>world</b>', 'level': 2}},
            {'type': 'list', 'data': {'style': 'unordered', 'items': ['one', 'two']}},
            {'type': 'code', 'data': {'code': 'print(1)', 'language': 'python'}},
            {'type': 'math', 'data': {'content': 'x^2'}},
            {'type': 'image', 'data': {'file': {'url': '/media/a.png'}, 'caption': 'Plot'}},
        ]}
        original = repr(legacy)
        markdown = editorjs_to_markdown(legacy)
        projected = markdown_to_editorjs(markdown)

        self.assertEqual(repr(legacy), original)
        self.assertIn('## Hello **world**', markdown)
        self.assertIn('```python', markdown)
        self.assertIn('$$\nx^2\n$$', markdown)
        self.assertEqual([block['type'] for block in projected['blocks']],
                         ['header', 'list', 'code', 'math', 'image'])
        self.assertEqual(markdown_image_urls(markdown), ['/media/a.png'])

    def test_sanitizes_raw_html_and_unsafe_links(self):
        rendered = render_markdown('<script>alert(1)</script> [bad](javascript:alert(1))')
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertIn('alert(1)', markdown_plain_text('<script>alert(1)</script>'))
        self.assertEqual(markdown_to_editorjs(''), {'blocks': []})
        with self.assertRaises(ValueError):
            markdown_to_editorjs({'blocks': []})

    def test_mentions_in_markdown_headings_and_lists_survive_projection(self):
        projected = markdown_to_editorjs('# Hi @alice\n\n- ping @bob')
        self.assertEqual(
            [mention['username'] for mention in parse_editorjs_text_mentions(projected)],
            ['alice', 'bob'],
        )

    def test_unknown_legacy_block_keeps_readable_text(self):
        self.assertEqual(editorjs_to_markdown({
            'blocks': [{'type': 'custom', 'data': {'text': 'Readable fallback'}}],
        }), 'Readable fallback')

    @patch('forum.services.utils.default_storage')
    def test_cleanup_only_deletes_urls_under_media_path(self, storage):
        from forum.services.utils import delete_files_from_urls
        storage.exists.return_value = True
        delete_files_from_urls([
            'https://other.example/media/plot.png', '/posts/plot.png',
            '/media/../posts/plot.png', '/media/plot.png',
        ])
        storage.delete.assert_called_once_with('plot.png')


class MarkdownAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            school_email='markdown@wpga.ca', password='markdown-pass',
            first_name='Markdown', last_name='Tester',
        )
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_title_only_posts_preserve_both_content_representations(self):
        for body in ({}, {'content': ''}, {'content': '   '}):
            with self.subTest(body=body):
                response = self.api.post(reverse('api_v2_create_post'), {
                    'title': 'Title only', **body,
                }, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                post = Post.objects.get(pk=response.data['id'])
                self.assertEqual(post.content_markdown, '')
                self.assertEqual(post.content, {'blocks': []})
                self.assertEqual(response.data['content'], '')
                legacy = self.api.get(reverse('api_post_detail', args=[post.id]))
                self.assertEqual(legacy.status_code, 200)
                self.assertEqual(legacy.data['content'], {'blocks': []})

    def test_title_only_posts_still_require_a_title_and_valid_content_type(self):
        for body in ({}, {'title': ''}, {'title': '   '},
                     {'title': 'Title', 'content': None},
                     {'title': 'Title', 'content': {'blocks': []}}):
            with self.subTest(body=body):
                response = self.api.post(reverse('api_v2_create_post'), body, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Post.objects.filter(author=self.user).exists())

    def test_poll_without_body_still_creates_options(self):
        response = self.api.post(reverse('api_v2_create_post'), {
            'title': 'Choose one',
            'poll_data': {'isPoll': True, 'question': 'Choose one', 'answers': ['One', 'Two']},
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['content'], '')
        self.assertEqual(len(response.data['poll_options']), 2)

    def test_feeds_reject_invalid_pagination(self):
        for route in ('api_v2_all_posts', 'api_v2_for_you', 'all_posts_api', 'for_you_api'):
            for field in ('page', 'limit'):
                for value in ('bad', '0', '-1', '1.5', ''):
                    with self.subTest(route=route, field=field, value=value):
                        response = self.api.get(reverse(route), {field: value})
                        self.assertEqual(response.status_code, 400, response.data)
                        self.assertIn(field, response.data)

    def test_feeds_accept_valid_pagination_and_empty_later_pages(self):
        post = Post.objects.create(title='Post', author=self.user, content={'blocks': []})
        for route in ('api_v2_all_posts', 'api_v2_for_you', 'all_posts_api', 'for_you_api'):
            with self.subTest(route=route):
                response = self.api.get(reverse(route), {'page': '1', 'limit': '1'})
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual([item['id'] for item in response.data['posts']], [post.id])
                response = self.api.get(reverse(route), {'page': '2', 'limit': '1'})
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['posts'], [])
                self.assertFalse(response.data['has_next'])

    @override_settings(LEGACY_APP_UPDATE_ONLY=True)
    def test_legacy_feed_shows_only_update_card_and_v2_feed_shows_posts(self):
        admin = User.objects.create_superuser(
            school_email='admin@wpga.ca', password='admin-pass',
            first_name='Admin', last_name='User',
        )
        post = Post.objects.create(
            title='Current post', author=self.user,
            content={'blocks': [{'type': 'paragraph', 'data': {'text': 'Current body'}}]},
        )

        for route in ('all_posts_api', 'for_you_api'):
            response = self.api.get(reverse(route))
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(len(response.data['posts']), 1)
            self.assertTrue(response.data['posts'][0]['title'].startswith('Update the app'))
            self.assertEqual(response.data['posts'][0]['preview_text'], '')
            self.assertEqual(response.data['posts'][0]['author']['id'], admin.id)
            self.assertFalse(response.data['has_next'])

        for route in ('api_v2_all_posts', 'api_v2_for_you'):
            response = self.api.get(reverse(route))
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual([item['id'] for item in response.data['posts']], [post.id])

        with override_settings(LEGACY_APP_UPDATE_ONLY=False):
            response = self.api.get(reverse('all_posts_api'))
            self.assertEqual([item['id'] for item in response.data['posts']], [post.id])


    def test_both_api_families_return_their_own_representation(self):
        response = self.api.post(reverse('api_v2_create_post'), {
            'title': 'Markdown post', 'content': 'Hello **world**',
            'allow_teacher': True,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        post = Post.objects.get(id=response.data['id'])
        self.assertEqual(post.content_markdown, 'Hello **world**')
        self.assertIsInstance(post.content, dict)
        self.assertEqual(response.data['content'], 'Hello **world**')

        legacy = self.api.get(reverse('api_post_detail', args=[post.id]))
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.data['content']['blocks'][0]['data']['text'],
                         'Hello <strong>world</strong>')

        edited = self.api.patch(reverse('api_v2_update_post', args=[post.id]), {
            'content': 'Edited ![plot](/media/plot.png)',
        }, format='json')
        self.assertEqual(edited.status_code, 200, edited.data)
        post.refresh_from_db()
        self.assertEqual(post.get_first_image_url(), '/media/plot.png')
        self.assertEqual(len([block for block in post.content['blocks']
                              if block['type'] == 'image']), 1)

        legacy_doc = {'blocks': [{'type': 'paragraph', 'data': {'text': 'Legacy edit'}}]}
        edited = self.api.patch(reverse('api_update_post', args=[post.id]), {
            'content': legacy_doc,
        }, format='json')
        self.assertEqual(edited.status_code, 200, edited.data)
        post.refresh_from_db()
        self.assertEqual(post.content, legacy_doc)
        self.assertEqual(post.content_markdown, 'Legacy edit')

    def test_backfill_preserves_json_for_posts_solutions_comments_and_replies(self):
        legacy = {'blocks': [{'type': 'paragraph', 'data': {'text': 'Old <b>content</b>'}}]}
        post = Post.objects.create(title='Old', author=self.user, content=legacy)
        solution = Solution.objects.create(post=post, author=self.user, content=legacy)
        comment = Comment.objects.create(solution=solution, author=self.user, content=legacy)
        reply = Comment.objects.create(
            solution=solution, author=self.user, parent=comment, content=legacy,
        )
        Post.objects.filter(pk=post.pk).update(content_markdown=None)
        from importlib import import_module
        migration = import_module('forum.migrations.0075_markdown_content')
        migration.backfill_markdown(apps, SimpleNamespace(connection=connection))
        for item in (post, solution, comment, reply):
            item.refresh_from_db()
            self.assertEqual(item.content, legacy)
            self.assertEqual(item.content_markdown, 'Old **content**')

    def test_markdown_post_body_is_searchable(self):
        post = Post(title='Question', author=self.user, content={})
        set_content_representations(post, 'A **distinctivegeometryterm** appears here.', 'markdown')
        post.save()
        rank = Post.objects.filter(pk=post.pk).annotate(
            rank=SearchRank(F('search_vector'), SearchQuery('distinctivegeometryterm')),
        ).values_list('rank', flat=True).get()
        self.assertGreater(rank, 0)

    def test_nested_solution_comment_and_reply_use_markdown(self):
        post = Post.objects.create(
            title='Question', author=self.user,
            content={'blocks': [{'type': 'paragraph', 'data': {'text': 'Question'}}]},
        )
        answer = self.api.post(reverse('api_v2_create_solution', args=[post.id]),
                               {'content': '**Answer**'}, format='json')
        self.assertEqual(answer.status_code, 201, answer.data)
        solution_id = answer.data['id']
        comment = self.api.post(reverse('api_v2_create_comment', args=[solution_id]),
                                {'content': 'Comment'}, format='json')
        self.assertEqual(comment.status_code, 201, comment.data)
        reply = self.api.post(reverse('api_v2_create_comment', args=[solution_id]),
                              {'content': '@markdown reply', 'parent_id': comment.data['id']},
                              format='json')
        self.assertEqual(reply.status_code, 201, reply.data)

        detail = self.api.get(reverse('api_v2_post_detail', args=[post.id]))
        self.assertEqual(detail.status_code, 200, detail.data)
        solution = detail.data['solutions'][0]
        self.assertEqual(solution['content'], '**Answer**')
        self.assertEqual(solution['comments'][0]['content'], 'Comment')
        self.assertEqual(solution['comments'][0]['replies'][0]['content'], '@markdown reply')
        legacy = self.api.get(reverse('api_post_detail', args=[post.id]))
        self.assertIsInstance(legacy.data['solutions'][0]['content'], dict)
        self.assertIsInstance(legacy.data['solutions'][0]['comments'][0]['content'], dict)

        self.assertEqual(Solution.objects.get(id=solution_id).content_markdown, '**Answer**')
        self.assertEqual(Comment.objects.get(id=comment.data['id']).content_markdown, 'Comment')

    def test_rejects_wrong_markdown_payload(self):
        response = self.api.post(reverse('api_v2_create_post'), {
            'title': 'Bad', 'content': {'blocks': []},
        }, format='json')
        self.assertEqual(response.status_code, 400)
        legacy = self.api.post(reverse('api_create_post'), {
            'title': 'Bad JSON', 'content': '{broken',
        }, format='json')
        self.assertEqual(legacy.status_code, 400)

    def test_web_solution_form_submits_markdown(self):
        post = Post.objects.create(
            title='Question', author=self.user,
            content={'blocks': [{'type': 'paragraph', 'data': {'text': 'Question'}}]},
        )
        self.client.force_login(self.user)
        page = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertContains(page, 'name="content_format" value="markdown"')
        response = self.client.post(reverse('create_solution', args=[post.id]), {
            'content': 'Web **answer**', 'content_format': 'markdown',
        })
        self.assertLess(response.status_code, 400)
        solution = Solution.objects.get(post=post)
        self.assertEqual(solution.content_markdown, 'Web **answer**')

    def test_web_detail_renders_sanitized_markdown(self):
        post = Post(title='Web Markdown', author=self.user, content={})
        set_content_representations(
            post, '**Safe** <script>alert("unsafe")</script> [link](javascript:alert(1))',
            'markdown',
        )
        post.save()
        self.api.logout()
        self.client.force_login(self.user)
        response = self.client.get(reverse('post_detail', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<strong>Safe</strong>', html=False)
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
