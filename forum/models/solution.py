from django.db import models


class Solution(models.Model):
    post = models.ForeignKey('forum.Post', on_delete=models.CASCADE, related_name='solutions')
    author = models.ForeignKey('forum.User', on_delete=models.CASCADE)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)

    def __str__(self):
        return f'Solution by {self.author.username} for {self.post.title}'
    
    def get_absolute_url(self):
        """
        Returns the URL to the specific solution element on the post detail page.
        """
        return f"{self.post.get_absolute_url()}#solution-{self.id}"
    
    def root_comments_count(self):
        return self.comments.filter(parent__isnull=True).count()


class SavedSolution(models.Model):
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name="saved_solutions")
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name="saves")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'solution')  # Ensure users can't save the same solution twice.

    def __str__(self):
        return f"{self.user.username} saved solution for {self.solution.post.title}"


class Comment(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey('forum.User', on_delete=models.CASCADE)
    content = models.JSONField() 
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies') 

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author.username}'
    
    @property
    def replies(self):
        return Comment.objects.filter(parent=self).order_by('created_at')
    
    def get_absolute_url(self):
        return f'#comment-{self.id}'
    
    def get_depth(self):
        """Calculate the nesting depth of this comment"""
        depth = 0
        parent = self.parent
        while parent:
            depth += 1
            parent = parent.parent
        return min(depth, 5)  # Limit maximum nesting depth to 5


class SolutionUpvote(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE)
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('solution', 'user')


class SolutionDownvote(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE)
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('solution', 'user')


class CommentUpvote(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('comment', 'user')
