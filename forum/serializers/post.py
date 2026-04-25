from rest_framework import serializers
from forum.models import Post
from django.utils.timezone import localtime
from forum.services.utils import process_post_preview
from .user import AnonUserSerializer, UserSerializer


class PostListSerializer(serializers.ModelSerializer):
    """Serializer for post list/feed views - matches paginate_posts structure"""
    author = serializers.SerializerMethodField()
    preview_text = serializers.SerializerMethodField()
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
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'author', 'preview_text', 
            'created_at', 'courses', 'reply_count', 'views', 'like_count', 
            'is_liked', 'solution_count', 'comment_count', 'solved', 'is_following',
            'first_image_url', 'is_anonymous', 'allow_teacher', 'poll_data'
        ]
    
    def get_author(self, obj):
        """Return author data with anonymous serializer if post is anonymous"""
        author_info = obj.get_author()
        
        # Use anonymous serializer if post is anonymous
        if author_info['is_anonymous']:
            return AnonUserSerializer(author_info['user'], context=self.context).data
        else:
            return UserSerializer(author_info['user'], context=self.context).data
    
    def get_preview_text(self, obj):
        return process_post_preview(obj)
    
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
            return obj.is_liked_by(request.user)
        return False
    
    def get_is_following(self, obj):
        """Check if the current user is following this post"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from forum.models import FollowedPost
            return FollowedPost.objects.filter(user=request.user, post=obj).exists()
        return False
    
    def get_like_count(self, obj):
        return obj.like_count()
    
    def get_solution_count(self, obj):
        return getattr(obj, 'solution_count', obj.solutions.count())
    
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
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content', 'author', 'courses', 'created_at',
            'solved', 'views', 'is_anonymous', 'allow_teacher', 'like_count', 'is_liked',
            'solution_count', 'comment_count', 'solutions', 'has_solution_from_user',
            'is_following', 'poll_options', 'poll_info', 'user_vote'
        ]
    
    def get_author(self, obj):
        """Return author data with anonymous serializer if post is anonymous"""
        author_info = obj.get_author()
        
        # Use anonymous serializer if post is anonymous
        if author_info['is_anonymous']:
            return AnonUserSerializer(author_info['user'], context=self.context).data
        else:
            return UserSerializer(author_info['user'], context=self.context).data
    
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
        return getattr(obj, 'solution_count', obj.solutions.count())
    
    def get_comment_count(self, obj):
        return getattr(obj, 'comment_count', 0)
    
    def get_solutions(self, obj):
        """Return solutions using appropriate serializer based on anonymity"""
        from django.db.models import F, Case, When, IntegerField
        from .solution import AnonSolutionSerializer, SolutionSerializer
        
        solutions = obj.solutions.select_related('author').annotate(
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
        
        # Add post to context for checking anonymity
        context = dict(self.context)
        context['post'] = obj
        
        # Serialize each solution with appropriate serializer
        solutions_data = []
        for solution in solutions:
            # Use anonymous serializer if post is anonymous and solution author is post author
            should_be_anon = obj.is_anonymous and solution.author_id == obj.author_id
            if should_be_anon:
                serializer = AnonSolutionSerializer(solution, context=context)
            else:
                serializer = SolutionSerializer(solution, context=context)
            solutions_data.append(serializer.data)
        
        return solutions_data
    
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


class AnonPostDetailSerializer(serializers.ModelSerializer):
    """Serializer for anonymous post detail views - when post.is_anonymous is True"""
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
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'content', 'author', 'courses', 'created_at',
            'solved', 'views', 'is_anonymous', 'like_count', 'is_liked',
            'solution_count', 'comment_count', 'solutions', 'has_solution_from_user',
            'is_following'
        ]
    
    def get_author(self, obj):
        """Always return anonymous author data"""
        author_info = obj.get_author()
        return AnonUserSerializer(author_info['user'], context=self.context).data
    
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
        return getattr(obj, 'solution_count', obj.solutions.count())
    
    def get_comment_count(self, obj):
        return getattr(obj, 'comment_count', 0)
    
    def get_solutions(self, obj):
        """Return solutions, using anonymous serializer for post author's solutions"""
        from django.db.models import F, Case, When, IntegerField
        from .solution import AnonSolutionSerializer, SolutionSerializer
        
        solutions = obj.solutions.select_related('author').annotate(
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
        
        # Add post to context for checking anonymity
        context = dict(self.context)
        context['post'] = obj
        
        # Serialize each solution with appropriate serializer
        solutions_data = []
        for solution in solutions:
            # Use anonymous serializer if solution author is post author
            should_be_anon = solution.author_id == obj.author_id
            if should_be_anon:
                serializer = AnonSolutionSerializer(solution, context=context)
            else:
                serializer = SolutionSerializer(solution, context=context)
            solutions_data.append(serializer.data)
        
        return solutions_data
    
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
