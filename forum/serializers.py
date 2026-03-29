from rest_framework import serializers
from .models import Post, Solution, Comment, User, UserProfile, Course, Notification, VolunteerPinMilestone, VolunteerResource, Poll, PollOption, PollVote
from django.utils.timezone import localtime
from .services.utils import process_post_preview
from django.conf import settings

# Constants
ANONYMOUS_PROFILE_PICTURE = f"{settings.MEDIA_URL}profile_pictures/default.png"

class CourseSerializer(serializers.ModelSerializer):
    is_experienced = serializers.SerializerMethodField()
    needs_help = serializers.SerializerMethodField()
    blocks = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'category', 'description', 'is_experienced', 'needs_help', 'blocks']
    
    def get_is_experienced(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            experienced_courses = getattr(request, '_experienced_courses', None)
            if experienced_courses is None:
                from .services.course_services import get_user_courses
                experienced_courses, _ = get_user_courses(request.user)
                request._experienced_courses = experienced_courses
            return obj in experienced_courses
        return False
    
    def get_needs_help(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            help_needed_courses = getattr(request, '_help_needed_courses', None)
            if help_needed_courses is None:
                from .services.course_services import get_user_courses
                _, help_needed_courses = get_user_courses(request.user)
                request._help_needed_courses = help_needed_courses
            return obj in help_needed_courses
        return False

class UserProfileSerializer(serializers.ModelSerializer):
    block_1A = CourseSerializer(read_only=True)
    block_1B = CourseSerializer(read_only=True)
    block_1D = CourseSerializer(read_only=True)
    block_1E = CourseSerializer(read_only=True)
    block_2A = CourseSerializer(read_only=True)
    block_2B = CourseSerializer(read_only=True)
    block_2C = CourseSerializer(read_only=True)
    block_2D = CourseSerializer(read_only=True)
    block_2E = CourseSerializer(read_only=True)
    grade_level = serializers.IntegerField(read_only=True)
    allow_schedule_comparison = serializers.BooleanField(read_only=True)
    profile_picture = serializers.SerializerMethodField()
    lunch_card = serializers.SerializerMethodField()
    has_wolfnet_password = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    can_compare = serializers.SerializerMethodField()
    initial_users = serializers.SerializerMethodField()
    schedule_blocks = serializers.SerializerMethodField()
    instagram_url = serializers.SerializerMethodField()
    snapchat_url = serializers.SerializerMethodField()
    linkedin_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'bio', 'points', 'is_moderator', 'created_at', 'updated_at',
            'background_hue', 'profile_picture', 'lunch_card',
            'block_1A', 'block_1B', 'block_1D', 'block_1E',
            'block_2A', 'block_2B', 'block_2C', 'block_2D', 'block_2E',
            'grade_level', 'allow_schedule_comparison', 'display_email',
            'has_wolfnet_password', 'stats', 'courses', 'recent_posts',
            'can_compare', 'initial_users', 'schedule_blocks',
            'instagram_url', 'snapchat_url', 'linkedin_url'
        ]
    
    def get_profile_picture(self, obj):
        """Return profile picture URL"""
        try:
            if obj.profile_picture:
                return obj.profile_picture.url
            return None
        except (AttributeError, FileNotFoundError, ValueError):
            return None
    
    def get_lunch_card(self, obj):
        """Return lunch card URL"""
        try:
            if obj.lunch_card:
                return obj.lunch_card.url
            return None
        except (AttributeError, FileNotFoundError, ValueError):
            return None
    
    def get_has_wolfnet_password(self, obj):
        """Check if user has wolfnet password set"""
        return bool(obj.wolfnet_password)
    
    def get_schedule_blocks(self, obj):
        """Return schedule blocks with course info"""
        blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        schedule_blocks = {}
        for block in blocks:
            course = getattr(obj, f'block_{block}', None)
            if course:
                schedule_blocks[f'block_{block}'] = {
                    'id': course.id,
                    'name': course.name,
                    'category': course.category,
                }
            else:
                schedule_blocks[f'block_{block}'] = None
        return schedule_blocks
    
    def get_stats(self, obj):
        """Return user stats"""
        from .models import Post, Solution
        posts_count = Post.objects.filter(author=obj.user).count()
        solutions_count = Solution.objects.filter(author=obj.user).count()
        return {
            'posts_count': posts_count,
            'solutions_count': solutions_count
        }
    
    def get_courses(self, obj):
        """Return user courses (experienced, help needed, schedule)"""
        from .models import UserCourseExperience, UserCourseHelp
        import json
        
        experienced_courses = UserCourseExperience.objects.filter(user=obj.user)
        help_needed_courses = UserCourseHelp.objects.filter(user=obj.user, active=True)
        
        # Get schedule courses using BlockSerializer
        serializer = BlockSerializer(obj)
        schedule_courses = serializer.data.get('schedule', {}) if serializer and serializer.data else {}
        
        return {
            'experienced_courses': [
                {
                    'id': exp.id,
                    'course': {
                        'id': exp.course.id,
                        'name': exp.course.name,
                        'category': exp.course.category
                    }
                } for exp in experienced_courses
            ],
            'help_needed_courses': [
                {
                    'id': help_req.id,
                    'course': {
                        'id': help_req.course.id,
                        'name': help_req.course.name,
                        'category': help_req.course.category
                    }
                } for help_req in help_needed_courses
            ],
            'schedule_courses': schedule_courses
        }
    
    def get_recent_posts(self, obj):
        """Return recent posts by user"""
        from .models import Post
        recent_posts = Post.objects.filter(
            author=obj.user,
            is_anonymous=False
        ).order_by('-created_at')[:3]
        
        return [
            {
                'id': post.id,
                'title': post.title,
                'created_at': post.created_at.isoformat(),
                'likes_count': post.like_count(),
                'solutions_count': post.solutions.count()
            } for post in recent_posts
        ]
    
    def get_can_compare(self, obj):
        """Check if the requesting user can compare schedules"""
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user != obj.user:
            return True
        return False
    
    def get_initial_users(self, obj):
        """Return initial users for comparison if applicable"""
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user != obj.user:
            return [
                {
                    'id': request.user.id,
                    'username': request.user.username,
                    'full_name': request.user.get_full_name(),
                    'school_email': request.user.school_email,
                    'profile_picture_url': request.user.userprofile.profile_picture.url if request.user.userprofile.profile_picture else None,
                },
                {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'full_name': obj.user.get_full_name(),
                    'school_email': obj.user.school_email,
                    'profile_picture_url': obj.profile_picture.url if obj.profile_picture else None,
                }
            ]
        return None
    
    def get_instagram_url(self, obj):
        """Get the full Instagram profile URL"""
        return obj.get_instagram_url()
    
    def get_snapchat_url(self, obj):
        """Get the full Snapchat profile URL"""
        return obj.get_snapchat_url()
    
    def get_linkedin_url(self, obj):
        """Get the LinkedIn profile URL"""
        return obj.get_linkedin_url()

class AnonUserProfileSerializer(serializers.ModelSerializer):
    """Serializer for anonymous user profiles - returns default/anonymous data"""
    block_1A = CourseSerializer(read_only=True)
    block_1B = CourseSerializer(read_only=True)
    block_1D = CourseSerializer(read_only=True)
    block_1E = CourseSerializer(read_only=True)
    block_2A = CourseSerializer(read_only=True)
    block_2B = CourseSerializer(read_only=True)
    block_2C = CourseSerializer(read_only=True)
    block_2D = CourseSerializer(read_only=True)
    block_2E = CourseSerializer(read_only=True)
    grade_level = serializers.SerializerMethodField()
    allow_schedule_comparison = serializers.BooleanField(read_only=True)
    profile_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'bio', 'points', 'is_moderator', 'created_at', 'updated_at',
            'background_hue', 'profile_picture',
            'block_1A', 'block_1B', 'block_1D', 'block_1E',
            'block_2A', 'block_2B', 'block_2C', 'block_2D', 'block_2E',
            'grade_level', 'allow_schedule_comparison'
        ]
    
    def get_profile_picture(self, obj):
        """Always return anonymous profile picture"""
        return ANONYMOUS_PROFILE_PICTURE
    
    def get_grade_level(self, obj):
        """Hide grade level for anonymous users"""
        return None

class UserSerializer(serializers.ModelSerializer):
    userprofile = UserProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'full_name',
            'school_email', 'personal_email', 'phone_number', 'student_id',
            'date_joined', 'userprofile', 'profile_picture_url', 'grade_level', 'is_teacher'
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_profile_picture_url(self, obj):
        """Return profile picture URL"""
        try:
            if obj.userprofile and obj.userprofile.profile_picture:
                return obj.userprofile.profile_picture.url
            return None
        except (AttributeError, FileNotFoundError, ValueError):
            return None

    def get_grade_level(self, obj):
        try:
            return obj.userprofile.grade_level if hasattr(obj, 'userprofile') else None
        except Exception:
            return None

class AnonUserSerializer(serializers.ModelSerializer):
    """Serializer for anonymous users - returns anonymous/default data"""
    userprofile = AnonUserProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'full_name',
            'school_email', 'personal_email', 'phone_number', 
            'date_joined', 'userprofile', 'profile_picture_url', 'grade_level'
        ]

    def get_username(self, obj):
        return ''
    
    def get_first_name(self, obj):
        return "Anonymous"

    def get_last_name(self,obj):
        return ""
    def get_full_name(self, obj):
        return "Anonymous"
    
    def get_profile_picture_url(self, obj):
        """Always return anonymous profile picture"""
        return ANONYMOUS_PROFILE_PICTURE

    def get_grade_level(self, obj):
        """Hide grade level for anonymous users"""
        return None

class BlockSerializer(serializers.ModelSerializer):
    """Serializer for user blocks data - returns user info + schedule blocks"""
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    grade_level = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['user_id', 'username', 'full_name', 'profile_picture_url', 'schedule', 'grade_level']
    
    def get_full_name(self, obj):
        return obj.user.get_full_name()
    
    def get_profile_picture_url(self, obj):
        try:
            if obj.profile_picture:
                return obj.profile_picture.url
            return None
        except (AttributeError, FileNotFoundError, ValueError):
            return None
    
    def get_schedule(self, obj):
        return {
            '1A': {
                'course': obj.block_1A.name if obj.block_1A else None,
                'course_id': obj.block_1A.id if obj.block_1A else None,
            },
            '1B': {
                'course': obj.block_1B.name if obj.block_1B else None,
                'course_id': obj.block_1B.id if obj.block_1B else None,
            },
            '1D': {
                'course': obj.block_1D.name if obj.block_1D else None,
                'course_id': obj.block_1D.id if obj.block_1D else None,
            },
            '1E': {
                'course': obj.block_1E.name if obj.block_1E else None,
                'course_id': obj.block_1E.id if obj.block_1E else None,
            },
            '2A': {
                'course': obj.block_2A.name if obj.block_2A else None,
                'course_id': obj.block_2A.id if obj.block_2A else None,
            },
            '2B': {
                'course': obj.block_2B.name if obj.block_2B else None,
                'course_id': obj.block_2B.id if obj.block_2B else None,
            },
            '2C': {
                'course': obj.block_2C.name if obj.block_2C else None,
                'course_id': obj.block_2C.id if obj.block_2C else None,
            },
            '2D': {
                'course': obj.block_2D.name if obj.block_2D else None,
                'course_id': obj.block_2D.id if obj.block_2D else None,
            },
            '2E': {
                'course': obj.block_2E.name if obj.block_2E else None,
                'course_id': obj.block_2E.id if obj.block_2E else None,
            },
        }

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
            from .models import FollowedPost
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
            from .models import FollowedPost
            return FollowedPost.objects.filter(user=request.user, post=obj).exists()
        return False

    def _get_poll_data(self, obj):
        """Get cached poll payload for detail views."""
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
            from .models import FollowedPost
            return FollowedPost.objects.filter(user=request.user, post=obj).exists()
        return False

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
        from .services.utils import selective_quote_replace
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
            from .models import SavedSolution
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
        from .services.utils import selective_quote_replace
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
            from .models import SavedSolution
            return SavedSolution.objects.filter(user=request.user, solution=obj).exists()
        return False

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

    def _serialize_voter(self, voter, profile_serializer):
        profile_picture_url = ANONYMOUS_PROFILE_PICTURE

        try:
            user_profile = voter.userprofile
        except Exception:
            user_profile = None

        if user_profile is not None:
            profile_picture_url = profile_serializer.get_profile_picture(user_profile) or ANONYMOUS_PROFILE_PICTURE

        return {
            'id': voter.id,
            'username' : voter.username,
            'full_name': voter.get_full_name() or voter.username,
            'profile_picture_url': profile_picture_url,
            'profile_url': voter.get_absolute_url()
        }
    
    def get_vote_count(self, obj):
        """Get the number of votes for this option"""
        return obj.votes.count()
    
    def get_percentage(self, obj):
        """Get the percentage of votes for this option"""
        poll = obj.poll
        total_votes = poll.votes.count()
        if total_votes == 0:
            return 0
        return round((obj.votes.count() / total_votes) * 100, 2)
    
    def get_user_voted(self, obj):
        """Check if the current user voted for this option using cached PollVote from context."""
        user_vote = self.context.get('user_vote')
        
        # If no user_vote in context, user is not authenticated or didn't vote
        if user_vote is None:
            return False
        
        # Check if this option is in the user's selected options
        return user_vote.selected_options.filter(id=obj.id).exists()

    def get_recent_voters(self, obj):
        """Get up to three most recent voters for this option when voting is public."""
        if not obj.poll.is_public_voting:
            return []

        recent_votes = obj.votes.select_related('user', 'user__userprofile').order_by('-updated_at')[:3]
        profile_serializer = UserProfileSerializer(context=self.context)
        recent_voters = []

        for vote in recent_votes:
            recent_voters.append(self._serialize_voter(vote.user, profile_serializer))

        return recent_voters

    def get_voters(self, obj):
        """Get all voters for this option when voting is public."""
        if not obj.poll.is_public_voting:
            return []

        votes = obj.votes.select_related('user', 'user__userprofile').order_by('-updated_at')
        profile_serializer = UserProfileSerializer(context=self.context)
        voters = []

        for vote in votes:
            voters.append(self._serialize_voter(vote.user, profile_serializer))

        return voters


class PollSerializer(serializers.ModelSerializer):
    """Serializer for poll display payload used across templates and views."""
    poll_options = serializers.SerializerMethodField()
    poll_info = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()

    class Meta:
        model = Poll
        fields = ['poll_options', 'poll_info', 'user_vote']

    def get_poll_info(self, obj):
        return {
            'allow_multiple_choice': obj.allow_multiple_choice,
            'is_public_voting': obj.is_public_voting,
            'total_votes': obj.votes.count()
        }

    def get_poll_options(self, obj):
        """Fetch user's vote once and pass it to child serializer to avoid N+1 queries."""
        request = self.context.get('request')
        user_vote = None
        
        if request and request.user.is_authenticated:
            try:
                user_vote = PollVote.objects.get(poll=obj, user=request.user)
            except PollVote.DoesNotExist:
                pass
        
        # Create child serializer context with cached user_vote
        child_context = self.context.copy()
        child_context['user_vote'] = user_vote
        child_context['poll_id'] = obj.id
        
        serializer = PollOptionSerializer(
            obj.options.all(),
            many=True,
            context=child_context
        )
        return serializer.data

    def get_user_vote(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        try:
            poll_vote = PollVote.objects.get(poll=obj, user=request.user)
            return {
                'id': poll_vote.id,
                'selected_option_ids': list(poll_vote.selected_options.values_list('id', flat=True))
            }
        except PollVote.DoesNotExist:
            return None


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