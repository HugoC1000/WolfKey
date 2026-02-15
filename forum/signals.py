from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Solution, Comment


# Update post last_activity_at when a solution is added or updated
@receiver(post_save, sender=Solution)
def update_post_activity_on_solution(sender, instance, created, **kwargs):
    """Update the parent post's last_activity_at when a solution is created"""
    if instance.post:
        instance.post.last_activity_at = timezone.now()
        instance.post.save(update_fields=['last_activity_at'])

# Update post last_activity_at when a comment is added
@receiver(post_save, sender=Comment)
def update_post_activity_on_comment(sender, instance, created, **kwargs):
    """Update the parent post's last_activity_at when a comment is created"""
    if created:
        # Comments are on solutions, solutions are on posts
        if instance.solution and instance.solution.post:
            instance.solution.post.last_activity_at = timezone.now()
            instance.solution.post.save(update_fields=['last_activity_at'])