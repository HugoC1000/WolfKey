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


class CommunityLunch(models.Model):
    """A date on which a community account meets during lunch."""
    community = models.ForeignKey(
        'forum.User',
        on_delete=models.CASCADE,
        related_name='community_lunches',
        limit_choices_to={'is_community_account': True},
    )
    date = models.DateField(db_index=True)
    location = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('community', 'date'),
                name='unique_community_lunch_date',
            ),
        ]
        ordering = ['date', 'community__first_name', 'community__last_name', 'community__username']

    def __str__(self):
        return f"{self.community.get_full_name()} lunch on {self.date.isoformat()}"
