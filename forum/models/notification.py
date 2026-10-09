from django.db import models


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('post', 'New Post'),
        ('solution', 'New Solution'),
        ('comment', 'New Comment'),
        ('reply', 'New Reply'),
        ('grade_update', 'Grade Update'),
        ('edit', 'Post Edit'),
        ('mention', 'Mention'),
        ('channel', 'Channel Mention'),
        ('everyone', 'Everyone Mention'),
        ('community', 'Community Post'),
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
