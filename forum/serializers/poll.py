from rest_framework import serializers
from django.db.models import Count, Prefetch
from forum.models import Poll, PollOption, PollVote, User
from .user import ANONYMOUS_PROFILE_PICTURE


class PollVoterSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'profile_picture_url', 'profile_url']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_profile_picture_url(self, obj):
        try:
            profile = obj.userprofile
            return profile.profile_picture.url if profile.profile_picture else ANONYMOUS_PROFILE_PICTURE
        except (AttributeError, FileNotFoundError, ValueError):
            return ANONYMOUS_PROFILE_PICTURE

    def get_profile_url(self, obj):
        return obj.get_absolute_url()


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

    def get_vote_count(self, obj):
        if hasattr(obj, 'serialized_vote_count'):
            return obj.serialized_vote_count
        return obj.votes.count()
    
    def get_percentage(self, obj):
        """Get the percentage of votes for this option"""
        total_votes = self.context.get('total_votes')
        if total_votes is None:
            total_votes = obj.poll.votes.count()
        if total_votes == 0:
            return 0
        return round((self.get_vote_count(obj) / total_votes) * 100, 2)
    
    def get_user_voted(self, obj):
        """Check if the current user voted for this option using cached PollVote from context."""
        return obj.id in self.context.get('selected_option_ids', set())

    def get_recent_voters(self, obj):
        """Get up to three most recent voters for this option when voting is public."""
        votes = getattr(obj, 'serialized_votes', [])[:3]
        return PollVoterSerializer(
            [vote.user for vote in votes], many=True, context=self.context
        ).data

    def get_voters(self, obj):
        """Get all voters for this option when voting is public."""
        votes = getattr(obj, 'serialized_votes', [])
        return PollVoterSerializer(
            [vote.user for vote in votes], many=True, context=self.context
        ).data


class PollSerializer(serializers.ModelSerializer):
    """Serializer for poll display payload used across templates and views."""
    poll_options = serializers.SerializerMethodField()
    poll_info = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Poll
        fields = ['poll_options', 'poll_info', 'user_vote']

    def _get_poll_state(self, obj):
        if not hasattr(self, '_poll_state_cache'):
            self._poll_state_cache = {}
        if obj.id in self._poll_state_cache:
            return self._poll_state_cache[obj.id]

        options = obj.options.annotate(
            serialized_vote_count=Count('votes', distinct=True)
        )
        if obj.is_public_voting:
            options = options.prefetch_related(Prefetch(
                'votes',
                queryset=PollVote.objects.select_related(
                    'user', 'user__userprofile'
                ).order_by('-updated_at'),
                to_attr='serialized_votes',
            ))

        user_vote = None
        selected_option_ids = set()
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_vote = PollVote.objects.filter(
                poll=obj,
                user=request.user,
            ).prefetch_related('selected_options').first()
            if user_vote:
                selected_option_ids = {
                    option.id for option in user_vote.selected_options.all()
                }

        state = {
            'options': list(options),
            'total_votes': obj.votes.count(),
            'selected_option_ids': selected_option_ids,
            'user_vote': {
                'id': user_vote.id,
                'selected_option_ids': sorted(selected_option_ids),
            } if user_vote else None,
        }
        self._poll_state_cache[obj.id] = state
        return state

    def get_poll_info(self, obj):
        state = self._get_poll_state(obj)
        return {
            'allow_multiple_choice': obj.allow_multiple_choice,
            'is_public_voting': obj.is_public_voting,
            'total_votes': state['total_votes'],
        }

    def get_poll_options(self, obj):
        state = self._get_poll_state(obj)
        child_context = self.context.copy()
        child_context['total_votes'] = state['total_votes']
        child_context['selected_option_ids'] = state['selected_option_ids']
        
        serializer = PollOptionSerializer(
            state['options'],
            many=True,
            context=child_context
        )
        return serializer.data

    def get_user_vote(self, obj):
        return self._get_poll_state(obj)['user_vote']


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
