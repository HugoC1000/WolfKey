from django.test import TestCase
from django.urls import reverse

from forum.models import Post, User
from forum.serializers import FeedUserSerializer, UserSerializer


class VerifiedBadgeTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            school_email='viewer@wpga.ca', password='password', first_name='View', last_name='Er'
        )
        self.paid_user = User.objects.create_user(
            school_email='paid@wpga.ca', password='password', first_name='Paid', last_name='User',
            is_paid_user=True,
        )
        self.community = User.objects.create_user(
            school_email='club@wpga.ca', password='password', first_name='Chess', last_name='Club',
            is_community_account=True,
        )
        self.client.force_login(self.viewer)

    def test_paid_status_is_exposed_in_public_author_and_profile_payloads(self):
        self.assertTrue(FeedUserSerializer(self.paid_user).data['is_paid_user'])
        self.assertTrue(UserSerializer(self.paid_user).data['is_paid_user'])

    def test_post_card_shows_badge_for_community_and_paid_authors_only(self):
        paid_post = Post.objects.create(title='Paid', content={'blocks': []}, author=self.paid_user)
        community_post = Post.objects.create(title='Community', content={'blocks': []}, author=self.community)
        viewer_post = Post.objects.create(title='Regular', content={'blocks': []}, author=self.viewer)
        anonymous_paid_post = Post.objects.create(
            title='Anonymous paid', content={'blocks': []}, author=self.paid_user, is_anonymous=True
        )

        response = self.client.get(reverse('all_posts'))

        self.assertContains(response, 'alt="Verified account"', count=2)
        self.assertContains(response, paid_post.title)
        self.assertContains(response, community_post.title)
        self.assertContains(response, viewer_post.title)
        self.assertContains(response, anonymous_paid_post.title)

    def test_profile_shows_badge_for_paid_and_community_accounts(self):
        paid_profile = self.client.get(reverse('profile', args=[self.paid_user.username]))
        community_profile = self.client.get(reverse('profile', args=[self.community.username]))
        regular_profile = self.client.get(reverse('profile', args=[self.viewer.username]))

        self.assertContains(paid_profile, 'Verified account')
        self.assertContains(community_profile, 'Verified account')
        self.assertNotContains(regular_profile, 'Verified account')
