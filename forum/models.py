from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.urls import reverse
import os


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
    
class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name='posts', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

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
        return reverse('post_detail', args=[self.id])
    
class SavedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')  # Ensure users can't save the same post twice.

    def __str__(self):
        return f"{self.user.username} saved {self.post.title}"

class File(models.Model):
    post = models.ForeignKey('Post', related_name='files', on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to='uploads/')
    temporary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    upload_session = models.CharField(max_length=100, blank=True)
    
    def delete(self, *args, **kwargs):
        # Delete actual file when model is deleted
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.file.name}"
    
    @property
    def filename(self):
        return os.path.basename(self.file.name)

class Solution(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='solutions')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    upvotes = models.IntegerField(default=0)

    def __str__(self):
        return f'Solution by {self.author.username} for {self.post.title}'

class Comment(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    upvotes = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.author.username}'

class SolutionUpvote(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('solution', 'user')

class CommentUpvote(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('comment', 'user')

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    points = models.IntegerField(default=0)
    is_moderator = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"
    
