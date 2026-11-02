import csv
import io
import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from forum.models import AnalyticsCoverage, AnalyticsEvent, Comment, Poll, PollOption, Post, Solution, User
from forum.services.analytics_service import METRICS, VANCOUVER, daily_rows, record_event, record_interaction
from forum.services.comment_services import vote_comment_service
from forum.services.poll_services import cast_poll_vote


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(school_email='analytics@wpga.ca', password='test-password',
                                             first_name='Analytics', last_name='User')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=self.user).key)
        self.coverage = AnalyticsCoverage.objects.get(pk=1)
        self.coverage.started_at = datetime(2026, 3, 1, tzinfo=VANCOUVER)
        self.coverage.save()

    def event(self, **overrides):
        data = dict(id=str(uuid.uuid4()), platform='web', event_type='screen_open', screen='home')
        data.update(overrides)
        return data

    def ingest(self, **overrides):
        return self.api.post('/api/analytics/events/', self.event(**overrides), format='json')

    def test_token_ingestion_derives_account_and_deduplicates(self):
        data = self.event()
        for _ in range(2):
            self.assertEqual(self.api.post('/api/analytics/events/', data, format='json').status_code, 200)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)
        self.assertEqual(AnalyticsEvent.objects.get().account_id, self.user.pk)

    def test_authentication_validation_and_csrf(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.post('/api/analytics/events/', self.event(), format='json').status_code, 401)
        for data in [self.event(screen='/profile/person'), self.event(platform='ios'),
                     self.event(event_type='post_interaction'), self.event(account_id=999),
                     self.event(event_type='volunteer_open', screen='home'),
                     self.event(query='private search')]:
            self.assertEqual(self.api.post('/api/analytics/events/', data, format='json').status_code, 400)
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post('/api/analytics/events/', self.event(), format='json').status_code, 403)
        from django.middleware.csrf import _get_new_csrf_string
        csrf = _get_new_csrf_string()
        browser.cookies['csrftoken'] = csrf
        self.assertEqual(browser.post('/api/analytics/events/', self.event(), format='json',
                                      HTTP_X_CSRFTOKEN=csrf).status_code, 200)

    def test_dates_distinct_users_feature_usage_and_platforms(self):
        timestamp = datetime(2026, 3, 8, 12, tzinfo=VANCOUVER)
        for platform in ('web', 'mobile'):
            for _ in range(2):
                AnalyticsEvent.objects.create(account_id=self.user.pk, platform=platform,
                    event_type='screen_open', screen='post_detail', occurred_at=timestamp)
                for event in ('match_open', 'profile_search', 'volunteer_open'):
                    AnalyticsEvent.objects.create(account_id=self.user.pk, platform=platform,
                        event_type=event, screen='profile', occurred_at=timestamp)
        row = list(daily_rows(date(2026, 3, 8), date(2026, 3, 8), list(METRICS), self.coverage.started_at))[0]
        self.assertEqual(row, ['2026-03-08', 1, 4, 4, 0, 1, 1, 1, 2, 2, 1, 1])

    def test_dst_boundaries_have_no_missing_or_duplicate_events(self):
        # Spring day has 23 hours; fall day has 25 hours, with two 01:30s.
        for start, instants in [
            (date(2026, 3, 8), ['2026-03-08T07:59:59+00:00', '2026-03-08T08:00:00+00:00',
                               '2026-03-09T06:59:59+00:00', '2026-03-09T07:00:00+00:00']),
            (date(2026, 11, 1), ['2026-11-01T06:59:59+00:00', '2026-11-01T08:30:00+00:00',
                                '2026-11-01T09:30:00+00:00', '2026-11-02T08:00:00+00:00']),
        ]:
            with self.subTest(start=start):
                AnalyticsEvent.objects.all().delete()
                for instant in instants:
                    AnalyticsEvent.objects.create(account_id=self.user.pk, platform='web', event_type='screen_open',
                                                  screen='home', occurred_at=datetime.fromisoformat(instant))
                rows = list(daily_rows(start - timedelta(days=1), start + timedelta(days=1),
                                      ['web_opens'], self.coverage.started_at))
                self.assertEqual([row[1] for row in rows], [1, 2, 1])

    def test_export_permissions_selection_bom_and_missing_history(self):
        url = '/admin/analytics/download/'
        today = timezone.localtime(timezone.now(), VANCOUVER).date()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/analytics/').status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename='export_analytics'))
        page = self.client.get('/admin/analytics/')
        self.assertContains(page, 'Download CSV')
        self.assertContains(self.client.get('/admin/'), '/admin/analytics/')
        self.coverage.started_at = datetime.combine(today, datetime.min.time(), VANCOUVER)
        self.coverage.save()
        params = {'start': today - timedelta(days=1), 'end': today,
                  'metrics': ['mobile_opens', 'unique_users']}
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn(f'{today}.csv', response['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0], ['date', 'unique_users', 'mobile_opens'])
        self.assertEqual(rows[1][1:], ['', ''])
        self.assertEqual(rows[2][1:], ['0', '0'])
        for bad in [dict(params, metrics=[]), dict(params, metrics=['unknown']),
                    dict(params, start='invalid'), dict(params, start=today + timedelta(days=1)),
                    dict(params, end=today + timedelta(days=1))]:
            self.assertEqual(self.client.get(url, bad).status_code, 400)
        self.user.is_superuser = True
        self.user.save()
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get('/admin/analytics/').status_code, 200)

    def test_analytics_failure_does_not_break_database_transaction(self):
        with transaction.atomic():
            with patch.object(AnalyticsEvent.objects, 'create', side_effect=DatabaseError('simulated')):
                with self.assertLogs('forum.services.analytics_service', level='ERROR'):
                    self.assertFalse(record_event(self.user, 'screen_open', 'home'))
            self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_interactions_web_legacy_v2_and_no_background_opens(self):
        post = Post.objects.create(author=self.user, title='Tracked post', content={'blocks': []})
        self.client.force_login(self.user)
        # Web likes, repeated likes and removals.
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                self.assertEqual(self.client.post(f'/posts/{post.pk}/like/').status_code, 200)
            self.assertEqual(self.client.post(f'/posts/{post.pk}/unlike/').status_code, 200)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)
        self.assertEqual(AnalyticsEvent.objects.get().platform, 'web')
        # Token API interaction is mobile. Fetching a post through either API is not a visible open.
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                self.assertEqual(self.api.post(f'/api/posts/{post.pk}/follow/').status_code, 200)
        for path in (f'/api/posts/{post.pk}/', f'/api/v2/posts/{post.pk}/'):
            self.assertEqual(self.api.get(path).status_code, 200)
        self.assertEqual(AnalyticsEvent.objects.count(), 2)
        self.assertEqual(AnalyticsEvent.objects.filter(platform='mobile').count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.api.post(f'/api/v2/posts/{post.pk}/solutions/create/', {'content': 'A useful answer'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(AnalyticsEvent.objects.count(), 3)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.api.post(f'/api/posts/{post.pk}/like/').status_code, 200)
            self.assertEqual(self.api.post('/api/posts/999999/like/').status_code, 404)
        self.assertEqual(AnalyticsEvent.objects.count(), 4)
        self.assertFalse(AnalyticsEvent.objects.filter(event_type='screen_open').exists())

    def test_poll_one_event_per_submission_and_comment_vote_removals(self):
        poll = Poll.objects.create(author=self.user, title='Poll', content={'blocks': []}, allow_multiple_choice=True)
        options = [PollOption.objects.create(poll=poll, text=str(i)).pk for i in range(2)]
        with self.captureOnCommitCallbacks(execute=True):
            cast_poll_vote(self.user, poll.pk, options)
            cast_poll_vote(self.user, poll.pk, options)
            cast_poll_vote(self.user, poll.pk, options[:1])  # edit
        self.assertEqual(AnalyticsEvent.objects.count(), 1)
        solution = Solution.objects.create(post=poll, author=self.user, content={'blocks': []})
        comment = Comment.objects.create(solution=solution, author=self.user, content={'blocks': []})
        with self.captureOnCommitCallbacks(execute=True):
            vote_comment_service(self.user, comment.pk, 'upvote')
            vote_comment_service(self.user, comment.pk, 'downvote')
            vote_comment_service(self.user, comment.pk, 'downvote')  # removal
        self.assertEqual(AnalyticsEvent.objects.count(), 3)

    def test_client_feature_events_and_no_personal_content(self):
        for event, screen in [('match_open', 'match'), ('match_open', 'profile'),
                              ('profile_search', 'explore'), ('volunteer_open', 'volunteer')]:
            self.assertEqual(self.ingest(event_type=event, screen=screen).status_code, 200)
        self.assertEqual(AnalyticsEvent.objects.count(), 4)

    def test_rolled_back_actions_do_not_record_interactions(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    record_interaction(self.user)
                    raise ValueError('business transaction rolled back')
            except ValueError:
                pass
        self.assertFalse(AnalyticsEvent.objects.exists())

    def test_product_pages_only_receive_screen_identifiers(self):
        from forum.context_processors import analytics
        factory = RequestFactory()
        for path, expected in [('/all-posts/', 'home'), ('/match/', 'match'),
                               ('/profile/private-username/', 'profile'),
                               ('/all-posts/fragment/', None), ('/api/search-users/', None),
                               ('/admin/analytics/', None)]:
            request = factory.get(path)
            request.user = self.user
            request.resolver_match = resolve(path)
            self.assertEqual(analytics(request).get('analytics_screen'), expected)
