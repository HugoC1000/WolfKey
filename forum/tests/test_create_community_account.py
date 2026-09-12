from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from forum.models import User


class CreateCommunityAccountCommandTests(TestCase):
    def test_recovery_email_can_be_reused(self):
        call_command(
            'create_community_account',
            name='Chemistry Club',
            username='chemistryclub',
            email='club-contact@example.com',
            password='Chem123',
            stdout=StringIO(),
        )
        call_command(
            'create_community_account',
            name='Physics Club',
            username='physicsclub',
            email='club-contact@example.com',
            password='Physics123',
            stdout=StringIO(),
        )

        self.assertEqual(
            User.objects.filter(personal_email='club-contact@example.com').count(),
            2,
        )
        self.assertTrue(
            User.objects.get(username='chemistryclub').is_community_account
        )
        self.assertTrue(
            User.objects.get(username='physicsclub').is_community_account
        )
