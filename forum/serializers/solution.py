from rest_framework import serializers
from forum.models import Comment, Solution
from django.utils.timezone import localtime
from .user import AnonymousAuthorSerializer, FeedUserSerializer


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    depth = serializers.SerializerMethodField()
    viewer_can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'author', 'created_at', 'parent',
            'replies', 'depth', 'viewer_can_edit'
        ]
    
    def get_author(self, obj):
        """Return author data, using anonymous serializer if appropriate"""
        post = self.context.get('post') or obj.solution.post
        should_be_anon = post.is_anonymous and obj.author_id == post.author_id
        
        if should_be_anon:
            return AnonymousAuthorSerializer(obj.author, context=self.context).data
        else:
            return FeedUserSerializer(obj.author, context=self.context).data
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_replies(self, obj):
        if hasattr(obj, 'detail_replies'):
            replies = obj.detail_replies
        else:
            replies = obj.replies.select_related(
                'author', 'author__userprofile', 'solution__post'
            )
        return CommentSerializer(replies, many=True, context=self.context).data
    
    def get_depth(self, obj):
        if hasattr(obj, 'detail_depth'):
            return obj.detail_depth
        return obj.get_depth()

    def get_viewer_can_edit(self, obj):
        request = self.context.get('request')
        return bool(
            request
            and request.user.is_authenticated
            and request.user.id == obj.author_id
        )


class SolutionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    processed_content = serializers.SerializerMethodField()
    viewer_has_upvoted = serializers.SerializerMethodField()
    viewer_has_downvoted = serializers.SerializerMethodField()
    root_comment_count = serializers.SerializerMethodField()
    viewer_can_edit = serializers.SerializerMethodField()
    
    class Meta:
        model = Solution
        fields = [
            'id', 'content', 'processed_content', 'author', 'created_at', 
            'upvotes', 'downvotes', 'comments', 'is_accepted', 'is_saved',
            'viewer_has_upvoted', 'viewer_has_downvoted', 'root_comment_count',
            'viewer_can_edit'
        ]
    
    def get_author(self, obj):
        """Return author data, using anonymous serializer if appropriate"""
        post = self.context.get('post') or obj.post
        should_be_anon = post.is_anonymous and obj.author_id == post.author_id
        
        if should_be_anon:
            return AnonymousAuthorSerializer(obj.author, context=self.context).data
        else:
            return FeedUserSerializer(obj.author, context=self.context).data
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_processed_content(self, obj):
        """Process solution content - handle string JSON and quote replacement"""
        from forum.services.utils import selective_quote_replace
        import json
        
        try:
            solution_content = obj.content
            if isinstance(solution_content, str):
                solution_content = selective_quote_replace(solution_content)
                solution_content = json.loads(solution_content)
            return solution_content
        except Exception as e:
            return obj.content
    
    def get_comments(self, obj):
        """Get formatted comments for this solution, using anon serializer when appropriate"""
        if hasattr(obj, 'detail_root_comments'):
            comments = obj.detail_root_comments
        else:
            comments = obj.comments.filter(parent__isnull=True).select_related(
                'author', 'author__userprofile', 'solution__post'
            ).order_by('created_at')
        return CommentSerializer(comments, many=True, context=self.context).data
    
    def get_is_accepted(self, obj):
        if hasattr(obj, 'detail_is_accepted'):
            return obj.detail_is_accepted
        return hasattr(obj, 'accepted_for') and obj.accepted_for is not None
    
    def get_is_saved(self, obj):
        """Check if the current user has saved this solution"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if hasattr(obj, 'detail_is_saved'):
                return obj.detail_is_saved
            from forum.models import SavedSolution
            return SavedSolution.objects.filter(user=request.user, solution=obj).exists()
        return False

    def get_viewer_has_upvoted(self, obj):
        if hasattr(obj, 'detail_viewer_has_upvoted'):
            return obj.detail_viewer_has_upvoted
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.solutionupvote_set.filter(user=request.user).exists()
        return False

    def get_viewer_has_downvoted(self, obj):
        if hasattr(obj, 'detail_viewer_has_downvoted'):
            return obj.detail_viewer_has_downvoted
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.solutiondownvote_set.filter(user=request.user).exists()
        return False

    def get_root_comment_count(self, obj):
        if hasattr(obj, 'detail_root_comments'):
            return len(obj.detail_root_comments)
        return obj.root_comments_count()

    def get_viewer_can_edit(self, obj):
        request = self.context.get('request')
        return bool(
            request
            and request.user.is_authenticated
            and request.user.id == obj.author_id
        )
