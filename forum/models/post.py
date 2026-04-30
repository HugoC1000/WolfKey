from django.db import models
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.urls import reverse


class Post(models.Model):
    """
    Parent post model with common attributes for all post types.
    Uses multi-table inheritance for StandardPost and Poll subclasses.
    """
    POST_TYPE_CHOICES = [
        ('standard', 'Standard Post'),
        ('poll', 'Poll'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.JSONField()
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='standard')
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey('forum.User', on_delete=models.CASCADE, null=True, blank=True)
    search_vector = SearchVectorField(null=True, blank=True)
    courses = models.ManyToManyField('forum.Course', related_name='posts', blank=True)
    is_anonymous = models.BooleanField(default=False)
    allow_teacher = models.BooleanField(
        default=True,
        help_text="Allow teachers to view this post"
    )
    solved = models.BooleanField(default=False)
    views = models.IntegerField(default=0)
    accepted_solution = models.OneToOneField(
        'forum.Solution',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='accepted_for'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        search_vector = (
            SearchVector('title', weight='A') +
            SearchVector('content', weight='B')
        )
        Post.objects.filter(id=self.id).update(search_vector=search_vector)

    def get_absolute_url(self):
        """Get URL for this post. Should be overridden in subclasses if needed."""
        return reverse('post_detail', args=[self.id])

    def like_count(self):
        """Get the number of likes on this post"""
        return self.likes.count()

    def is_liked_by(self, user):
        """Check if a specific user has liked this post"""
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()

    def get_author(self, ignore_anonymous=False):
        """Return author object with anonymous profile picture if post is anonymous
        
        Args:
            ignore_anonymous: If True, return actual author info even for anonymous posts.
                            If False (default), return anonymous indicator for anonymous posts.
        """
        if self.is_anonymous and not ignore_anonymous:
            return {
                'user': self.author,
                'is_anonymous': True
            }
        return {
            'user': self.author,
            'is_anonymous': False
        }
    
    def get_first_image_url(self):
        """Extract the first image URL from the post content JSON"""
        try:
            import json
            
            content = self.content
            if isinstance(content, str):
                content = json.loads(content)
            
            if not isinstance(content, dict) or 'blocks' not in content:
                return None
            
            for block in content.get('blocks', []):
                if isinstance(block, dict) and block.get('type') == 'image':
                    if 'data' in block and 'file' in block['data']:
                        file_data = block['data']['file']
                        if isinstance(file_data, dict) and 'url' in file_data:
                            return file_data['url']
                        elif isinstance(file_data, str):
                            return file_data
            
            return None
            
        except (json.JSONDecodeError, AttributeError, TypeError):
            return None


class StandardPost(Post):
    """
    Standard discussion post type. Inherits from Post.
    """

    class Meta:
        verbose_name = "Standard Post"
        verbose_name_plural = "Standard Posts"


class SavedPost(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Ensure users can't save the same post twice.

    def __str__(self):
        return f"{self.user.username} saved {self.post.title}"


class FollowedPost(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name="followed_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="followers")
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Ensure users can't follow the same post twice.

    def __str__(self):
        return f"{self.user.username} follows {self.post.title}"


class PostLike(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name="liked_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')
