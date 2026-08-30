from rest_framework import serializers
from django.urls import reverse

from forum.models import CommunityLunch
from .user import safe_file_url


class CommunityLunchSerializer(serializers.ModelSerializer):
    """Lunch date plus the public profile information needed by schedule cards."""
    community = serializers.SerializerMethodField()
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = CommunityLunch
        fields = ['id', 'date', 'location', 'community', 'profile_url']

    def get_community(self, obj):
        community = obj.community
        return {
            'id': community.id,
            'username': community.username,
            'full_name': community.get_full_name(),
            'profile_picture_url': safe_file_url(community.userprofile.profile_picture),
        }

    def get_profile_url(self, obj):
        return reverse('profile', kwargs={'username': obj.community.username})


def serialize_community_lunches_for_schedule(target_date, blocks):
    from forum.services.community_services import get_community_lunches_for_date
    lunches = get_community_lunches_for_date(target_date, any(blocks))
    return CommunityLunchSerializer(lunches, many=True).data
