from rest_framework import serializers

from forum.models import Petition, PollVote
from .poll import PollVoterSerializer


class PetitionSerializer(serializers.ModelSerializer):
    """Normalized display payload for petition cards and detail views."""

    support_count = serializers.SerializerMethodField()
    oppose_count = serializers.SerializerMethodField()
    total_participants = serializers.SerializerMethodField()
    support_percentage = serializers.SerializerMethodField()
    support_vote_percentage = serializers.SerializerMethodField()
    oppose_vote_percentage = serializers.SerializerMethodField()
    viewer_stance = serializers.SerializerMethodField()
    support_voters = serializers.SerializerMethodField()
    oppose_voters = serializers.SerializerMethodField()

    class Meta:
        model = Petition
        fields = [
            'support_goal',
            'support_count',
            'oppose_count',
            'total_participants',
            'support_percentage',
            'support_vote_percentage',
            'oppose_vote_percentage',
            'viewer_stance',
            'support_voters',
            'oppose_voters',
        ]

    def _get_state(self, obj):
        if not hasattr(self, '_petition_state_cache'):
            self._petition_state_cache = {}
        if obj.id in self._petition_state_cache:
            return self._petition_state_cache[obj.id]

        votes = list(
            PollVote.objects.filter(poll=obj)
            .select_related('user', 'user__userprofile')
            .prefetch_related('selected_options')
            .order_by('-created_at')
        )
        support_voters = []
        oppose_voters = []
        viewer_stance = None
        request = self.context.get('request')

        for vote in votes:
            labels = {option.text for option in vote.selected_options.all()}
            stance = None
            if Petition.SUPPORT in labels:
                stance = 'support'
            elif Petition.OPPOSE in labels:
                stance = 'oppose'
            if stance is None:
                continue

            if stance == 'support':
                support_voters.append(vote.user)
            else:
                oppose_voters.append(vote.user)

            if (
                request
                and request.user.is_authenticated
                and vote.user_id == request.user.id
            ):
                viewer_stance = stance

        state = {
            'support_voters': support_voters,
            'oppose_voters': oppose_voters,
            'viewer_stance': viewer_stance,
        }
        self._petition_state_cache[obj.id] = state
        return state

    def get_support_count(self, obj):
        return len(self._get_state(obj)['support_voters'])

    def get_support_voters(self, obj):
        return PollVoterSerializer(self._get_state(obj)['support_voters'], many=True, context=self.context).data

    def get_oppose_voters(self, obj):
        return PollVoterSerializer(self._get_state(obj)['oppose_voters'], many=True, context=self.context).data

    def get_oppose_count(self, obj):
        return len(self._get_state(obj)['oppose_voters'])

    def get_total_participants(self, obj):
        state = self._get_state(obj)
        return len(state['support_voters']) + len(state['oppose_voters'])

    def get_support_percentage(self, obj):
        if not obj.support_goal:
            return None
        percentage = self.get_support_count(obj) / obj.support_goal * 100
        return round(min(percentage, 100), 2)

    def _get_vote_percentage(self, obj, stance):
        total = self.get_total_participants(obj)
        if not total:
            return 0
        count = self.get_support_count(obj) if stance == 'support' else self.get_oppose_count(obj)
        return round(count / total * 100, 2)

    def get_support_vote_percentage(self, obj):
        return self._get_vote_percentage(obj, 'support')

    def get_oppose_vote_percentage(self, obj):
        return self._get_vote_percentage(obj, 'oppose')

    def get_viewer_stance(self, obj):
        return self._get_state(obj)['viewer_stance']


def serialize_petition_display_data(post_or_petition, request=None):
    if not post_or_petition:
        return None

    petition = post_or_petition if isinstance(post_or_petition, Petition) else None
    if petition is None:
        if getattr(post_or_petition, 'post_type', None) != 'petition':
            return None
        try:
            petition = Petition.objects.get(poll_ptr_id=post_or_petition.id)
        except Petition.DoesNotExist:
            return None

    context = {'request': request} if request is not None else {}
    return PetitionSerializer(petition, context=context).data
