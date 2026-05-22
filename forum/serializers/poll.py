from rest_framework import serializers
from forum.models import Poll, PollOption, PollVote
from django.conf import settings

ANONYMOUS_PROFILE_PICTURE = f"{settings.MEDIA_URL}profile_pictures/default.png"


class PollOptionSerializer(serializers.ModelSerializer):
    """Serializer for poll options"""
    vote_count = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    user_voted = serializers.SerializerMethodField()
    recent_voters = serializers.SerializerMethodField()
    voters = serializers.SerializerMethodField()
    
    class Meta:
        model = PollOption
        fields = ['id', 'text', 'vote_count', 'percentage', 'user_voted', 'recent_voters', 'voters']

    def _serialize_voter(self, voter, profile_serializer):
        profile_picture_url = ANONYMOUS_PROFILE_PICTURE

        try:
            user_profile = voter.userprofile
        except Exception:
            user_profile = None

        if user_profile is not None:
            profile_picture_url = profile_serializer.get_profile_picture(user_profile) or ANONYMOUS_PROFILE_PICTURE

        return {
            'id': voter.id,
            'username': voter.username,
            'full_name': voter.get_full_name() or voter.username,
            'profile_picture_url': profile_picture_url,
            'profile_url': voter.get_absolute_url()
        }
    
    def get_vote_count(self, obj):
        """Get the number of votes for this option"""
        return obj.votes.count()
    
    def get_percentage(self, obj):
        """Get the percentage of votes for this option"""
        poll = obj.poll
        total_votes = poll.votes.count()
        if total_votes == 0:
            return 0
        return round((obj.votes.count() / total_votes) * 100, 2)
    
    def get_user_voted(self, obj):
        """Check if the current user voted for this option using cached PollVote from context."""
        user_vote = self.context.get('user_vote')
        
        # If no user_vote in context, user is not authenticated or didn't vote
        if user_vote is None:
            return False
        
        # Check if this option is in the user's selected options
        return user_vote.selected_options.filter(id=obj.id).exists()

    def get_recent_voters(self, obj):
        """Get up to three most recent voters for this option when voting is public."""
        if not obj.poll.is_public_voting:
            return []

        recent_votes = obj.votes.select_related('user', 'user__userprofile').order_by('-updated_at')[:3]
        from .user import UserProfileSerializer
        profile_serializer = UserProfileSerializer(context=self.context)
        recent_voters = []

        for vote in recent_votes:
            recent_voters.append(self._serialize_voter(vote.user, profile_serializer))

        return recent_voters

    def get_voters(self, obj):
        """Get all voters for this option when voting is public."""
        if not obj.poll.is_public_voting:
            return []

        votes = obj.votes.select_related('user', 'user__userprofile').order_by('-updated_at')
        from .user import UserProfileSerializer
        profile_serializer = UserProfileSerializer(context=self.context)
        voters = []

        for vote in votes:
            voters.append(self._serialize_voter(vote.user, profile_serializer))

        return voters


class PollSerializer(serializers.ModelSerializer):
    """Serializer for poll display payload used across templates and views."""
    poll_options = serializers.SerializerMethodField()
    poll_info = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Poll
        fields = ['poll_options', 'poll_info', 'user_vote']

    def get_poll_info(self, obj):
        return {
            'allow_multiple_choice': obj.allow_multiple_choice,
            'is_public_voting': obj.is_public_voting,
            'total_votes': obj.votes.count()
        }

    def get_poll_options(self, obj):
        """Fetch user's vote once and pass it to child serializer to avoid N+1 queries."""
        request = self.context.get('request')
        user_vote = None
        
        if request and request.user.is_authenticated:
            try:
                user_vote = PollVote.objects.get(poll=obj, user=request.user)
            except PollVote.DoesNotExist:
                pass
        
        # Create child serializer context with cached user_vote
        child_context = self.context.copy()
        child_context['user_vote'] = user_vote
        child_context['poll_id'] = obj.id
        
        serializer = PollOptionSerializer(
            obj.options.all(),
            many=True,
            context=child_context
        )
        return serializer.data

    def get_user_vote(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        try:
            poll_vote = PollVote.objects.get(poll=obj, user=request.user)
            return {
                'id': poll_vote.id,
                'selected_option_ids': list(poll_vote.selected_options.values_list('id', flat=True))
            }
        except PollVote.DoesNotExist:
            return None


def serialize_poll_display_data(post_or_poll, request=None):
    """Build poll display payload from a Post or Poll instance using one serializer."""
    if not post_or_poll:
        return None

    poll = post_or_poll if isinstance(post_or_poll, Poll) else None

    if poll is None:
        if getattr(post_or_poll, 'post_type', None) != 'poll':
            return None
        try:
            poll = Poll.objects.get(post_ptr_id=post_or_poll.id)
        except Poll.DoesNotExist:
            return None

    context = {'request': request} if request is not None else {}
    return PollSerializer(poll, context=context).data


def attach_poll_data_to_posts(posts, serialized_posts):
    """Attach serializer-provided poll payload onto post objects for template rendering."""
    poll_data_by_post_id = {
        serialized_post.get('id'): serialized_post.get('poll_data')
        for serialized_post in serialized_posts
    }

    for post in posts:
        post.poll_data = poll_data_by_post_id.get(post.id)

    return posts
