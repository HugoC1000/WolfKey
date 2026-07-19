from rest_framework import serializers
from forum.models import Post
from django.utils.timezone import localtime
from forum.services.utils import process_post_preview, process_post_preview_html
from .user import AnonymousAuthorSerializer, FeedUserSerializer


class PostListSerializer(serializers.ModelSerializer):
    """Serializer for post list/feed views - matches paginate_posts structure"""
    author = serializers.SerializerMethodField()
    preview_text = serializers.SerializerMethodField()
    preview_html = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    solution_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    solved = serializers.SerializerMethodField()
    first_image_url = serializers.SerializerMethodField()
    poll_data = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    mentions = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'author', 'preview_text', 'preview_html',
            'created_at', 'courses', 'reply_count', 'views', 'like_count', 
            'is_liked', 'solution_count', 'comment_count', 'solved', 'is_following',
            'first_image_url', 'is_anonymous', 'allow_teacher', 'poll_data',
            'followers_count', 'mentions'
        ]
    
    def get_author(self, obj):
        """Return author data with anonymous serializer if post is anonymous"""
        if obj.is_anonymous:
            return AnonymousAuthorSerializer(obj.author, context=self.context).data
        return FeedUserSerializer(obj.author, context=self.context).data
    
    def get_preview_text(self, obj):
        return getattr(obj, 'preview_text', None) or process_post_preview(obj)
    
    def get_preview_html(self, obj):
        return getattr(obj, 'preview_html', None) or process_post_preview_html(obj)

    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_courses(self, obj):
        from .user import CourseSerializer
        return CourseSerializer(obj.courses.all(), many=True, context=self.context).data
    
    def get_reply_count(self, obj):
        return getattr(obj, 'total_response_count', 0)
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if hasattr(obj, 'is_liked_by_user'):
                return obj.is_liked_by_user
            return obj.is_liked_by(request.user)
        return False
    
    def get_is_following(self, obj):
        """Check if the current user is following this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if hasattr(obj, 'is_following'):
                return obj.is_following
            from forum.models import FollowedPost
            return FollowedPost.objects.filter(user=request.user, post=obj).exists()
        return False
    
    def get_like_count(self, obj):
        return obj.like_count()
    
    def get_solution_count(self, obj):
        if hasattr(obj, 'solution_count'):
            return obj.solution_count
        return obj.solutions.count()
    
    def get_comment_count(self, obj):
        return getattr(obj, 'comment_count', 0)
    
    def get_solved(self, obj):
        return obj.solved
    
    def get_first_image_url(self, obj):
        """Extract the first image URL from the post content JSON"""
        return obj.get_first_image_url()

    def get_poll_data(self, obj):
        """Get normalized poll payload for list/card display."""
        from .poll import serialize_poll_display_data
        request = self.context.get('request')
        return serialize_poll_display_data(obj, request=request)

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_mentions(self, obj):
        """Get all mentions in this post"""
        from forum.services.mention_service import fetch_mentions_for_content
        return fetch_mentions_for_content(obj)

class PostDetailSerializer(serializers.ModelSerializer):
    """Serializer for individual post views"""
    author = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    solution_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    solutions = serializers.SerializerMethodField()
    has_solution_from_user = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    poll_options = serializers.SerializerMethodField()
    poll_info = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    mentions = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content', 'author', 'courses', 'created_at',
            'solved', 'views', 'is_anonymous', 'allow_teacher', 'like_count', 'is_liked',
            'solution_count', 'comment_count', 'solutions', 'has_solution_from_user',
            'is_following', 'poll_options', 'poll_info', 'user_vote', 'mentions'
        ]
    
    def get_author(self, obj):
        """Return author data with anonymous serializer if post is anonymous"""
        if obj.is_anonymous:
            return AnonymousAuthorSerializer(obj.author, context=self.context).data
        return FeedUserSerializer(obj.author, context=self.context).data
    
    def get_courses(self, obj):
        from .user import CourseSerializer
        return CourseSerializer(obj.courses.all(), many=True, context=self.context).data
    
    def get_created_at(self, obj):
        return localtime(obj.created_at).isoformat()
    
    def get_like_count(self, obj):
        return obj.like_count()
    
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_liked_by(request.user)
        return False
    
    def get_solution_count(self, obj):
        if hasattr(obj, 'solution_count'):
            return obj.solution_count
        return obj.solutions.count()
    
    def get_comment_count(self, obj):
        return getattr(obj, 'comment_count', 0)
    
    def get_solutions(self, obj):
        """Return solutions using appropriate serializer based on anonymity"""
        from django.db.models import F, Case, When, IntegerField
        from .solution import SolutionSerializer
        
        solutions = obj.solutions.select_related('author', 'post').annotate(
            vote_score=F('upvotes') - F('downvotes')
        ).order_by(
            Case(
                When(id=obj.accepted_solution_id, then=0),
                default=1,
                output_field=IntegerField(),
            ),
            '-vote_score',
            '-created_at'
        )
        
        return SolutionSerializer(solutions, many=True, context=self.context).data
    
    def get_has_solution_from_user(self, obj):
        """Check if the current user has submitted a solution"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.solutions.filter(author=request.user).exists()
        return False
    
    def get_is_following(self, obj):
        """Check if the current user is following this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from forum.models import FollowedPost
            return FollowedPost.objects.filter(user=request.user, post=obj).exists()
        return False

    def _get_poll_data(self, obj):
        """Get cached poll payload for detail views."""
        from .poll import serialize_poll_display_data
        
        if obj.post_type != 'poll':
            return None

        if not hasattr(self, '_poll_data_cache'):
            self._poll_data_cache = {}

        if obj.id not in self._poll_data_cache:
            request = self.context.get('request')
            self._poll_data_cache[obj.id] = serialize_poll_display_data(obj, request=request)

        return self._poll_data_cache[obj.id]
    
    def get_poll_options(self, obj):
        """Get poll options if this is a poll"""
        poll_data = self._get_poll_data(obj)
        return poll_data.get('poll_options') if poll_data else None
    
    def get_poll_info(self, obj):
        """Get poll-specific information if this is a poll"""
        poll_data = self._get_poll_data(obj)
        return poll_data.get('poll_info') if poll_data else None
    
    def get_user_vote(self, obj):
        """Get the current user's vote on this poll if applicable"""
        poll_data = self._get_poll_data(obj)
        return poll_data.get('user_vote') if poll_data else None

    def get_mentions(self, obj):
        """Get all mentions in this post"""
        from forum.services.mention_service import fetch_mentions_for_content
        return fetch_mentions_for_content(obj)
