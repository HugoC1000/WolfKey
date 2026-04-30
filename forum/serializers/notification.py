from rest_framework import serializers
from forum.models import Notification, VolunteerPinMilestone, VolunteerResource
from django.utils.timezone import localtime
from .user import AnonUserSerializer, UserSerializer


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for user notifications"""
    sender = serializers.SerializerMethodField()
    post_title = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    message_text = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'sender', 'notification_type', 'post', 'solution', 'comment',
            'message', 'message_text', 'created_at', 'is_read', 'post_title'
        ]
    
    def get_sender(self, obj):
        """Return sender data, using anonymous serializer if notification is for anonymous post"""
        # Check if notification is related to an anonymous post
        post = obj.post
        if not post:
            # If notification is for a solution or comment, get the post from there
            if obj.solution:
                post = obj.solution.post
            elif obj.comment:
                post = obj.comment.solution.post if obj.comment.solution else None
        
        # Use anonymous serializer if post is anonymous and sender is post author
        should_be_anon = (post and post.is_anonymous and 
                         obj.sender_id == post.author_id)
        
        if should_be_anon:
            return AnonUserSerializer(obj.sender, context=self.context).data
        else:
            return UserSerializer(obj.sender, context=self.context).data
    
    def get_post_title(self, obj):
        """Get the related post title if available"""
        if obj.post:
            return obj.post.title
        return None
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_message_text(self, obj):
        """Strip HTML tags from message"""
        from django.utils.html import strip_tags
        return strip_tags(obj.message)


class VolunteerPinMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for volunteer pin milestones"""
    achieved = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = VolunteerPinMilestone
        fields = ['id', 'name', 'hours_required', 'has_other_requirements', 'achieved', 'progress_percentage']
    
    def get_achieved(self, obj):
        """Check if user has achieved this milestone"""
        user_hours = self.context.get('user_hours', 0)
        return user_hours >= obj.hours_required
    
    def get_progress_percentage(self, obj):
        """Calculate progress percentage to this milestone"""
        user_hours = self.context.get('user_hours', 0)
        if user_hours >= obj.hours_required:
            return 100
        return min(100, (user_hours / obj.hours_required) * 100) if obj.hours_required > 0 else 0


class VolunteerResourceSerializer(serializers.ModelSerializer):
    """Serializer for volunteer resources"""
    
    class Meta:
        model = VolunteerResource
        fields = ['id', 'title', 'url', 'description', 'display_order']
