from django.db import models
from django.core.exceptions import ValidationError
from .post import Post


class Poll(Post):
    """
    Poll post type. Inherits from Post and adds poll-specific features like
    voting options, public/private voting, and multiple choice support.
    """
    is_public_voting = models.BooleanField(
        default=True,
        help_text="If True, voting is public and results visible to all. If False, voting is private."
    )
    allow_multiple_choice = models.BooleanField(
        default=False,
        help_text="If True, users can select multiple options (multiselect). If False, only one option allowed."
    )

    class Meta:
        verbose_name = "Poll"
        verbose_name_plural = "Polls"

    def save(self, *args, **kwargs):
        if self.post_type == 'petition':
            self.allow_multiple_choice = False
            self.is_public_voting = True
        return super().save(*args, **kwargs)

    def get_poll_options(self):
        """Get all poll options for this poll"""
        return self.options.all()

    def get_user_vote(self, user):
        """Get the vote record for a specific user"""
        try:
            return self.votes.get(user=user)
        except PollVote.DoesNotExist:
            return None

    def get_vote_summary(self):
        """Get summary of poll options with vote counts"""
        summary = []
        total_votes = self.votes.count()
        
        for option in self.options.all():
            vote_count = option.votes.count()
            percentage = (vote_count / total_votes * 100) if total_votes > 0 else 0
            summary.append({
                'option': option,
                'vote_count': vote_count,
                'percentage': percentage
            })
        
        return summary


class PollOption(models.Model):
    """
    Individual option/choice in a poll
    """
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500, help_text="The option text/choice")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Poll Option"
        verbose_name_plural = "Poll Options"

    def __str__(self):
        return f"{self.poll.title} - {self.text}"

    def save(self, *args, **kwargs):
        if self.poll.post_type == 'petition':
            if self.text not in ('Support', 'Oppose'):
                raise ValidationError('Petition options must be Support or Oppose')
            duplicate = self.poll.options.filter(text=self.text).exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError(f'The {self.text} petition option already exists')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.poll.post_type == 'petition':
            raise ValidationError('Petition stance options cannot be deleted')
        return super().delete(*args, **kwargs)


class PollVote(models.Model):
    """
    Represents a user's vote in a poll. Supports multiselect by using ManyToMany relationship.
    """
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey('forum.User', on_delete=models.CASCADE, related_name='poll_votes')
    selected_options = models.ManyToManyField(
        PollOption,
        related_name='votes',
        help_text="The option(s) selected by the user"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['poll', 'user']  # One vote per user per poll
        verbose_name = "Poll Vote"
        verbose_name_plural = "Poll Votes"

    def __str__(self):
        return f"{self.user.username} voted on {self.poll.title}"
