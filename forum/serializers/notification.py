from rest_framework import serializers
from forum.models import Notification
from django.utils.timezone import localtime
from .user import AnonymousAuthorSerializer, FeedUserSerializer


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
    
    def _get_related_post(self, obj):
        if obj.post_id:
            return obj.post
        if obj.solution_id:
            return obj.solution.post
        if obj.comment_id and obj.comment.solution_id:
            return obj.comment.solution.post
        return None

    def get_sender(self, obj):
        """Return sender data, masking the author of an anonymous post."""
        post = self._get_related_post(obj)
        # Use anonymous serializer if post is anonymous and sender is post author
        should_be_anon = (post and post.is_anonymous and 
                         obj.sender_id == post.author_id)
        
        if should_be_anon:
            return AnonymousAuthorSerializer(obj.sender, context=self.context).data
        else:
            return FeedUserSerializer(obj.sender, context=self.context).data
    
    def get_post_title(self, obj):
        """Get the related post title if available"""
        post = self._get_related_post(obj)
        return post.title if post else None
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_message_text(self, obj):
        """Strip HTML tags from message"""
        from django.utils.html import strip_tags
        return strip_tags(obj.message)
