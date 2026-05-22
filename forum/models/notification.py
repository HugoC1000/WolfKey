from django.db import models
from django.utils import timezone


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('post', 'New Post'),
        ('solution', 'New Solution'),
        ('comment', 'New Comment'),
        ('reply', 'New Reply'),
        ('grade_update', 'Grade Update'),
        ('edit', 'Post Edit'),
    )
    
    recipient = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey('forum.Post', on_delete=models.CASCADE, null=True, blank=True)
    solution = models.ForeignKey('forum.Solution', on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey('forum.Comment', on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


class UpdateAnnouncement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    version = models.CharField(max_length=20)  # e.g., "1.2.0"
    release_date = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-release_date']


class UserUpdateView(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE)
    update = models.ForeignKey(UpdateAnnouncement, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'update']
