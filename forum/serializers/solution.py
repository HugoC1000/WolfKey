from rest_framework import serializers
from forum.models import Comment, Solution
from django.utils.timezone import localtime
from .user import AnonUserSerializer, UserSerializer


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    depth = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'author', 'created_at', 'parent',
            'replies', 'depth'
        ]
    
    def get_author(self, obj):
        """Return author data, using anonymous serializer if appropriate"""
        post = self.context.get('post')
        # Check if this comment should be anonymous
        should_be_anon = (post and post.is_anonymous and 
                         obj.author_id == post.author_id)
        
        if should_be_anon:
            return AnonUserSerializer(obj.author, context=self.context).data
        else:
            return UserSerializer(obj.author, context=self.context).data
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_replies(self, obj):
        if hasattr(obj, 'replies'):
            post = self.context.get('post')
            replies_data = []
            for reply in obj.replies.all():
                # Check if reply should be anonymous
                should_be_anon = (post and post.is_anonymous and 
                                 reply.author_id == post.author_id)
                if should_be_anon:
                    serializer = AnonCommentSerializer(reply, context=self.context)
                else:
                    serializer = CommentSerializer(reply, context=self.context)
                replies_data.append(serializer.data)
            return replies_data
        return []
    
    def get_depth(self, obj):
        return obj.get_depth()


class AnonCommentSerializer(serializers.ModelSerializer):
    """Serializer for anonymous comments - when comment author is post author and post is anonymous"""
    author = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    depth = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'author', 'created_at', 'parent',
            'replies', 'depth'
        ]
    
    def get_author(self, obj):
        """Return anonymous author data"""
        return AnonUserSerializer(obj.author, context=self.context).data
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_replies(self, obj):
        """Recursively serialize replies, using anon serializer when appropriate"""
        if hasattr(obj, 'replies'):
            post = self.context.get('post')
            replies_data = []
            for reply in obj.replies.all():
                # Check if reply should be anonymous
                should_be_anon = (post and post.is_anonymous and 
                                 reply.author_id == post.author_id)
                if should_be_anon:
                    serializer = AnonCommentSerializer(reply, context=self.context)
                else:
                    serializer = CommentSerializer(reply, context=self.context)
                replies_data.append(serializer.data)
            return replies_data
        return []
    
    def get_depth(self, obj):
        return obj.get_depth()


class SolutionSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    processed_content = serializers.SerializerMethodField()
    
    class Meta:
        model = Solution
        fields = [
            'id', 'content', 'processed_content', 'author', 'created_at', 
            'upvotes', 'downvotes', 'comments', 'is_accepted', 'is_saved'
        ]
    
    def get_author(self, obj):
        """Return author data, using anonymous serializer if appropriate"""
        post = self.context.get('post')
        # Check if this solution should be anonymous
        should_be_anon = (post and post.is_anonymous and 
                         obj.author_id == post.author_id)
        
        if should_be_anon:
            return AnonUserSerializer(obj.author, context=self.context).data
        else:
            return UserSerializer(obj.author, context=self.context).data
    
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
        comments = obj.comments.select_related('author').order_by('created_at')
        post = self.context.get('post')
        comments_data = []
        
        for comment in comments:
            # Check if comment should be anonymous
            should_be_anon = (post and post.is_anonymous and 
                             comment.author_id == post.author_id)
            if should_be_anon:
                serializer = AnonCommentSerializer(comment, context=self.context)
            else:
                serializer = CommentSerializer(comment, context=self.context)
            comments_data.append(serializer.data)
        
        return comments_data
    
    def get_is_accepted(self, obj):
        return hasattr(obj, 'accepted_for') and obj.accepted_for is not None
    
    def get_is_saved(self, obj):
        """Check if the current user has saved this solution"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from forum.models import SavedSolution
            return SavedSolution.objects.filter(user=request.user, solution=obj).exists()
        return False


class AnonSolutionSerializer(serializers.ModelSerializer):
    """Serializer for anonymous solutions - when solution author is post author and post is anonymous"""
    author = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    processed_content = serializers.SerializerMethodField()
    
    class Meta:
        model = Solution
        fields = [
            'id', 'content', 'processed_content', 'author', 'created_at', 
            'upvotes', 'downvotes', 'comments', 'is_accepted', 'is_saved'
        ]
    
    def get_author(self, obj):
        """Return anonymous author data"""
        return AnonUserSerializer(obj.author, context=self.context).data
    
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
        comments = obj.comments.select_related('author').order_by('created_at')
        post = self.context.get('post')
        comments_data = []
        
        for comment in comments:
            # Check if comment should be anonymous
            should_be_anon = (post and post.is_anonymous and 
                             comment.author_id == post.author_id)
            if should_be_anon:
                serializer = AnonCommentSerializer(comment, context=self.context)
            else:
                serializer = CommentSerializer(comment, context=self.context)
            comments_data.append(serializer.data)
        
        return comments_data
    
    def get_is_accepted(self, obj):
        return hasattr(obj, 'accepted_for') and obj.accepted_for is not None
    
    def get_is_saved(self, obj):
        """Check if the current user has saved this solution"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from forum.models import SavedSolution
            return SavedSolution.objects.filter(user=request.user, solution=obj).exists()
        return False
