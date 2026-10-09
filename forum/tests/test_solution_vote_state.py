from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from forum.models import Post, Solution, User


class SolutionVoteStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            password='votepass',
            school_email='solution-voter@wpga.ca',
            first_name='Solution',
            last_name='Voter',
        )
        self.post = Post.objects.create(title='Vote state', content='{}', author=self.user)
        self.solution = Solution.objects.create(
            post=self.post,
            author=self.user,
            content={'blocks': [{'type': 'paragraph', 'data': {'text': 'Answer'}}]},
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def get_solution(self):
        response = self.client.get(reverse('api_post_detail', args=[self.post.id]))
        self.assertEqual(response.status_code, 200)
        return response.data['solutions'][0]

    def vote(self, vote_type):
        response = self.client.post(
            reverse('api_vote_solution', args=[self.solution.id]),
            {'vote_type': vote_type},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_vote_state_survives_post_reload_and_switches(self):
        self.assertEqual(self.get_solution()['vote_state'], 'none')

        upvote = self.vote('upvote')
        self.assertEqual(upvote['vote_state'], 'upvoted')
        self.assertEqual(self.get_solution()['vote_state'], 'upvoted')

        downvote = self.vote('downvote')
        self.assertEqual(downvote['vote_state'], 'downvoted')
