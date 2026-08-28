from django.db import models


class CommunityFollow(models.Model):
    """A user's opt-in to posts from one community account."""
    user = models.ForeignKey(
        'forum.User', on_delete=models.CASCADE, related_name='followed_communities'
    )
    community = models.ForeignKey(
        'forum.User', on_delete=models.CASCADE, related_name='community_followers',
        limit_choices_to={'is_community_account': True},
    )
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'community')

    def __str__(self):
        return f"{self.user} follows {self.community}"


class CommunitySubscription(models.Model):
    """A user's email opt-in for a community account's mailing list."""
    user = models.ForeignKey(
        'forum.User', on_delete=models.CASCADE, related_name='community_subscriptions'
    )
    community = models.ForeignKey(
        'forum.User', on_delete=models.CASCADE, related_name='mailing_list_subscribers',
        limit_choices_to={'is_community_account': True},
    )
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'community')

    def __str__(self):
        return f"{self.user} mailing-list subscription to {self.community}"
