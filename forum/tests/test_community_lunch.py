from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.conf import settings
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from forum.models import CommunityFollow, CommunityLunch, CommunitySubscription, User
from forum.services.community_services import (
    add_community_lunch_service,
    cleanup_expired_community_lunches,
    delete_community_lunch_service,
    get_community_lunches_for_date,
    update_community_lunch_service,
)


class CommunityLunchTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            school_email='member@wpga.ca', password='password', first_name='Member', last_name='User'
        )
        self.community = User.objects.create_user(
            school_email='club@wpga.ca', password='password', first_name='Chess', last_name='Club',
            is_community_account=True,
        )
        self.inactive_community = User.objects.create_user(
            school_email='inactive@wpga.ca', password='password', first_name='Inactive', last_name='Club',
            is_community_account=True, is_active=False,
        )
        self.today = timezone.localdate()

    def test_lunches_are_date_specific_and_exclude_inactive_communities(self):
        CommunityLunch.objects.create(community=self.community, date=self.today, location='Room 101')
        CommunityLunch.objects.create(community=self.community, date=self.today + timedelta(days=1))
        CommunityLunch.objects.create(community=self.inactive_community, date=self.today)

        lunches = list(get_community_lunches_for_date(self.today, is_school_day=True))
        self.assertEqual([lunch.community_id for lunch in lunches], [self.community.id])
        self.assertFalse(get_community_lunches_for_date(self.today, is_school_day=False).exists())

    def test_owner_can_add_update_and_delete_lunches_and_others_cannot(self):
        tomorrow = self.today + timedelta(days=1)
        result = add_community_lunch_service(self.community, tomorrow.isoformat(), 'Library')
        self.assertNotIn('error', result)
        lunch = result['lunch']
        result = update_community_lunch_service(self.community, lunch.id, 'Room 101')
        self.assertEqual(result['lunch'].location, 'Room 101')

        result = delete_community_lunch_service(self.member, lunch.id)
        self.assertIn('error', result)
        self.assertTrue(CommunityLunch.objects.filter(id=lunch.id).exists())

        result = delete_community_lunch_service(self.community, lunch.id)
        self.assertNotIn('error', result)
        self.assertFalse(CommunityLunch.objects.filter(id=lunch.id).exists())

    def test_owner_api_manages_individual_lunches(self):
        token = Token.objects.create(user=self.community)
        response = self.client.post(
            reverse('api_community_lunches'),
            {'date': self.today.isoformat(), 'location': 'Room 101'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertEqual(response.status_code, 201)
        lunch_id = response.json()['lunch']['id']

        response = self.client.patch(
            reverse('api_community_lunch_detail', args=[lunch_id]),
            {'date': (self.today + timedelta(days=1)).isoformat(), 'location': 'Library'},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['lunch']['date'], (self.today + timedelta(days=1)).isoformat())
        self.assertEqual(response.json()['lunch']['location'], 'Library')

        response = self.client.delete(
            reverse('api_community_lunch_detail', args=[lunch_id]),
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(CommunityLunch.objects.filter(id=lunch_id).exists())

    def test_date_update_converts_unique_constraint_race_to_validation_error(self):
        lunch = CommunityLunch.objects.create(
            community=self.community,
            date=self.today,
            location='Room 101',
        )

        with patch.object(CommunityLunch, 'save', side_effect=IntegrityError):
            result = update_community_lunch_service(
                self.community,
                lunch.id,
                date_value=self.today + timedelta(days=1),
            )

        self.assertEqual(result, {'error': 'That lunch date is already listed.'})

    def test_lunch_api_rejects_non_community_accounts_and_blank_locations(self):
        member_token = Token.objects.create(user=self.member)
        response = self.client.get(
            reverse('api_community_lunches'),
            HTTP_AUTHORIZATION=f'Token {member_token.key}',
        )
        self.assertEqual(response.status_code, 403)

        community_token = Token.objects.create(user=self.community)
        response = self.client.post(
            reverse('api_community_lunches'),
            {'date': self.today.isoformat(), 'location': ''},
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {community_token.key}',
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_lunches_are_deleted(self):
        expired = CommunityLunch.objects.create(
            community=self.community,
            date=self.today - timedelta(days=1),
            location='Old room',
        )
        cleanup_expired_community_lunches()
        self.assertFalse(CommunityLunch.objects.filter(id=expired.id).exists())

    def test_date_logic_uses_vancouver_timezone(self):
        self.assertEqual(settings.TIME_ZONE, 'America/Vancouver')

    @patch('forum.views.schedule_views.get_block_order_for_day')
    def test_web_schedule_includes_lunches_only_on_school_days(self, mock_schedule):
        CommunityLunch.objects.create(community=self.community, date=self.today, location='Room 101')
        mock_schedule.return_value = {
            'blocks': ['1A'], 'times': ['8:30'], 'early_dismissal': False, 'late_start': False,
        }
        response = self.client.get(reverse('daily_schedule_view', args=[self.today.isoformat()]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['community_lunches'][0]['community']['id'], self.community.id)

        mock_schedule.return_value = {
            'blocks': [None], 'times': [None], 'early_dismissal': False, 'late_start': False,
        }
        response = self.client.get(reverse('daily_schedule_view', args=[self.today.isoformat()]))
        self.assertEqual(response.json()['community_lunches'], [])

    @patch('forum.api.schedule.is_ceremonial_uniform_required', return_value=False)
    @patch('forum.api.schedule.process_schedule_for_user', return_value=[])
    @patch('forum.api.schedule.get_block_order_for_day')
    def test_mobile_schedule_apis_do_not_return_lunches(self, mock_schedule, _mock_processed, _mock_uniform):
        CommunityLunch.objects.create(community=self.community, date=self.today, location='Room 101')
        token = Token.objects.create(user=self.member)
        mock_schedule.return_value = {
            'blocks': ['1A'], 'times': ['8:30'], 'early_dismissal': False, 'late_start': False,
        }
        daily_response = self.client.get(
            reverse('api_get_daily_schedule', args=[self.today.isoformat()]),
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )
        response = self.client.get(
            reverse('api_get_and_process_schedule', args=[self.member.id]),
            {'date': self.today.isoformat()},
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(daily_response.status_code, 200)
        self.assertNotIn('community_lunches', daily_response.json())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('community_lunches', response.json())

    @patch('forum.api.community.get_block_order_for_day')
    def test_date_lunch_api_returns_multiple_communities_after_schedule(self, mock_schedule):
        second_community = User.objects.create_user(
            school_email='math@wpga.ca', password='password', first_name='Math', last_name='Club',
            is_community_account=True,
        )
        first_lunch = CommunityLunch.objects.create(
            community=self.community, date=self.today, location='Room 101'
        )
        second_lunch = CommunityLunch.objects.create(
            community=second_community, date=self.today, location='Library'
        )
        token = Token.objects.create(user=self.member)
        mock_schedule.return_value = {
            'blocks': ['1A'], 'times': ['8:30'], 'early_dismissal': False, 'late_start': False,
        }

        response = self.client.get(
            reverse('api_community_lunches_for_date', args=[self.today.isoformat()]),
            HTTP_AUTHORIZATION=f'Token {token.key}',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {lunch['id'] for lunch in response.json()['lunches']},
            {first_lunch.id, second_lunch.id},
        )

    def test_profile_follow_sets_profile_state_and_mailing_list(self):
        self.client.login(school_email='member@wpga.ca', password='password')
        response = self.client.get(reverse('profile', args=[self.community.username]))
        self.assertContains(response, 'Join')

        response = self.client.post(reverse('toggle_community_follow', args=[self.community.id]), {
            'next': reverse('profile', args=[self.community.username]),
        })
        self.assertRedirects(response, reverse('profile', args=[self.community.username]))
        self.assertTrue(CommunityFollow.objects.filter(user=self.member, community=self.community).exists())
        self.assertTrue(CommunitySubscription.objects.filter(user=self.member, community=self.community, is_active=True).exists())

        response = self.client.get(reverse('profile', args=[self.community.username]))
        self.assertContains(response, 'Joined')
