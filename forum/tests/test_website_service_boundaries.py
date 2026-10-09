from django.test import TestCase
from django.urls import reverse

from forum.models import Post, User, VolunteerPinMilestone, VolunteerResource


class WebsiteServiceBoundaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            school_email='owner-boundary@wpga.ca', first_name='Owner', last_name='Student', password='password123',
        )
        self.other = User.objects.create_user(
            school_email='other-boundary@wpga.ca', first_name='Other', last_name='Student', password='password123',
        )
        self.post = Post.objects.create(title='Keep this post', content={'blocks': []}, author=self.owner)

    def test_post_delete_keeps_authorization_and_deletes_for_owner(self):
        url = reverse('delete_post', args=[self.post.id])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(url), reverse('all_posts'), fetch_redirect_response=False)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())

    def test_volunteer_admin_actions_save_and_remove_data(self):
        self.owner.is_staff = True
        self.owner.save(update_fields=['is_staff'])
        self.client.force_login(self.owner)
        self.client.post(reverse('create_milestone'), {'name': 'Silver', 'hours_required': '25'})
        milestone = VolunteerPinMilestone.objects.get(name='Silver')
        self.client.post(reverse('update_milestone', args=[milestone.id]), {
            'name': 'Gold', 'hours_required': '30', 'has_other_requirements': 'on',
        })
        milestone.refresh_from_db()
        self.assertEqual((milestone.name, milestone.hours_required, milestone.has_other_requirements), ('Gold', 30, True))
        self.client.post(reverse('create_resource'), {'title': 'Guide', 'url': 'https://example.com/guide'})
        resource = VolunteerResource.objects.get(title='Guide')
        self.client.post(reverse('delete_resource', args=[resource.id]))
        self.assertFalse(VolunteerResource.objects.filter(id=resource.id).exists())

    def test_updates_card_and_acknowledgment_route_are_removed(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse('all_posts'))
        self.assertNotContains(page, 'updateOverlay')
        self.assertEqual(self.client.post('/api/acknowledge-update/').status_code, 404)
