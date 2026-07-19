from rest_framework import serializers

from forum.models import VolunteerPinMilestone, VolunteerResource


class VolunteerPinMilestoneSerializer(serializers.ModelSerializer):
    """Serialize volunteer milestones with user-specific progress."""
    achieved = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = VolunteerPinMilestone
        fields = [
            'id', 'name', 'hours_required', 'has_other_requirements',
            'achieved', 'progress_percentage',
        ]

    def get_achieved(self, obj):
        return self.context.get('user_hours', 0) >= obj.hours_required

    def get_progress_percentage(self, obj):
        user_hours = self.context.get('user_hours', 0)
        if user_hours >= obj.hours_required:
            return 100
        return min(100, (user_hours / obj.hours_required) * 100) if obj.hours_required > 0 else 0


class VolunteerResourceSerializer(serializers.ModelSerializer):
    """Serialize links to volunteer resources."""

    class Meta:
        model = VolunteerResource
        fields = ['id', 'title', 'url', 'description', 'display_order']
