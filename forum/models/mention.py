from django.db import models


class Mention(models.Model):
    """
    Tracks when a user is mentioned in a post, solution, or comment.
    
    Mentions are extracted from EditorJS content marks and stored here for:
    - Quick lookups (e.g., "who mentioned me?")
    - Deduplication (same user mentioned multiple times = one record)
    - Notification tracking
    - Analytics
    """
    CONTENT_TYPES = [
        ('post', 'Post'),
        ('solution', 'Solution'),
        ('comment', 'Comment'),
    ]
    
    # Who mentioned whom
    author = models.ForeignKey(
        'forum.User',
        on_delete=models.CASCADE,
        related_name='mentions_made',
        help_text="User who made the mention"
    )
    mentioned_user = models.ForeignKey(
        'forum.User',
        on_delete=models.CASCADE,
        related_name='mentions_received',
        help_text="User who was mentioned"
    )
    
    # What was mentioned (one of: post, solution, or comment)
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPES,
        help_text="Type of content containing the mention"
    )
    post = models.ForeignKey(
        'forum.Post',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='mentions',
        help_text="If content_type='post', the post being mentioned"
    )
    solution = models.ForeignKey(
        'forum.Solution',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='mentions',
        help_text="If content_type='solution', the solution being mentioned"
    )
    comment = models.ForeignKey(
        'forum.Comment',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='mentions',
        help_text="If content_type='comment', the comment being mentioned"
    )
    
    # Context
    is_anonymous = models.BooleanField(
        default=False,
        help_text="True if the mention was in anonymous content"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensure one mention record per unique (author, mentioned_user, content_type, content_id)
        unique_together = ('author', 'mentioned_user', 'content_type', 'post', 'solution', 'comment')
        
        # Index for fast lookups: "who mentioned me?"
        indexes = [
            models.Index(fields=['mentioned_user', 'created_at']),
            models.Index(fields=['author', 'created_at']),
        ]
        
        ordering = ['-created_at']
    
    def __str__(self):
        content_repr = getattr(self, self.content_type)
        return f"{self.author.username} mentioned {self.mentioned_user.username} in {self.content_type}"
    
    def get_content_object(self):
        """Get the actual content object (Post, Solution, or Comment)"""
        return getattr(self, self.content_type)
