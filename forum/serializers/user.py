from rest_framework import serializers
from forum.models import User, UserProfile, Course
from django.conf import settings
from django.db.models import Count

ANONYMOUS_PROFILE_PICTURE = f"{settings.MEDIA_URL}profile_pictures/default.png"
USER_SCHEDULE_BLOCKS = ('1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E')


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
                from forum.services.course_services import get_user_courses
                experienced_courses, _ = get_user_courses(request.user)
                request._experienced_courses = experienced_courses
            return obj in experienced_courses
        return False
    
    def get_needs_help(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            help_needed_courses = getattr(request, '_help_needed_courses', None)
            if help_needed_courses is None:
                from forum.services.course_services import get_user_courses
                _, help_needed_courses = get_user_courses(request.user)
                request._help_needed_courses = help_needed_courses
            return obj in help_needed_courses
        return False


class UserProfileSerializer(serializers.ModelSerializer):
    """Public profile data safe to embed when exposing another user."""
    block_1A = serializers.SerializerMethodField()
    block_1B = serializers.SerializerMethodField()
    block_1D = serializers.SerializerMethodField()
    block_1E = serializers.SerializerMethodField()
    block_2A = serializers.SerializerMethodField()
    block_2B = serializers.SerializerMethodField()
    block_2C = serializers.SerializerMethodField()
    block_2D = serializers.SerializerMethodField()
    block_2E = serializers.SerializerMethodField()
    grade_level = serializers.IntegerField(read_only=True)
    allow_schedule_comparison = serializers.BooleanField(read_only=True)
    profile_picture = serializers.SerializerMethodField()
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
            'background_hue', 'profile_picture',
            'block_1A', 'block_1B', 'block_1D', 'block_1E',
            'block_2A', 'block_2B', 'block_2C', 'block_2D', 'block_2E',
            'grade_level', 'allow_schedule_comparison',
            'stats', 'courses', 'recent_posts',
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
    
    def _should_hide_schedule(self, obj):
        """Check if schedule fields should be hidden based on privacy settings"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return True
        if request.user == obj.user:
            return False
        return not obj.allow_schedule_comparison
    
    def _get_block(self, obj, block_name):
        """Helper to get a block field with privacy checks"""
        if self._should_hide_schedule(obj):
            return None
        
        course = getattr(obj, f'block_{block_name}', None)
        if course:
            serializer = CourseSerializer(course, context=self.context)
            return serializer.data
        return None
    
    def get_block_1A(self, obj):
        return self._get_block(obj, '1A')
    
    def get_block_1B(self, obj):
        return self._get_block(obj, '1B')
    
    def get_block_1D(self, obj):
        return self._get_block(obj, '1D')
    
    def get_block_1E(self, obj):
        return self._get_block(obj, '1E')
    
    def get_block_2A(self, obj):
        return self._get_block(obj, '2A')
    
    def get_block_2B(self, obj):
        return self._get_block(obj, '2B')
    
    def get_block_2C(self, obj):
        return self._get_block(obj, '2C')
    
    def get_block_2D(self, obj):
        return self._get_block(obj, '2D')
    
    def get_block_2E(self, obj):
        return self._get_block(obj, '2E')
    
    def get_schedule_blocks(self, obj):
        """Return schedule blocks with course info, respecting privacy settings"""
        if self._should_hide_schedule(obj):
            return None
        
        schedule_blocks = {}
        for block in USER_SCHEDULE_BLOCKS:
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
        from forum.models import Post, Solution
        posts_count = Post.objects.filter(author=obj.user).count()
        solutions_count = Solution.objects.filter(author=obj.user).count()
        return {
            'posts_count': posts_count,
            'solutions_count': solutions_count
        }
    
    def get_courses(self, obj):
        """Return user courses (experienced, help needed, schedule)"""
        from forum.models import UserCourseExperience, UserCourseHelp
        
        experienced_courses = UserCourseExperience.objects.filter(
            user=obj.user
        ).select_related('course')
        help_needed_courses = UserCourseHelp.objects.filter(
            user=obj.user,
            active=True,
        ).select_related('course')
        
        # Get schedule courses using the canonical user schedule serializer.
        serializer = UserScheduleSerializer(obj, context=self.context)
        schedule_courses = (
            {} if self._should_hide_schedule(obj)
            else serializer.data.get('schedule', {}) if serializer and serializer.data else {}
        )
        
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
        from forum.models import Post
        recent_posts = Post.objects.filter(
            author=obj.user,
            is_anonymous=False
        ).annotate(
            serialized_likes_count=Count('likes', distinct=True),
            serialized_solutions_count=Count('solutions', distinct=True),
        ).order_by('-created_at')[:3]
        
        return [
            {
                'id': post.id,
                'title': post.title,
                'created_at': post.created_at.isoformat(),
                'likes_count': post.serialized_likes_count,
                'solutions_count': post.serialized_solutions_count,
            } for post in recent_posts
        ]
    
    def get_can_compare(self, obj):
        """Check if the requesting user can compare schedules"""
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user != obj.user:
            return obj.allow_schedule_comparison
        return False
    
    def get_initial_users(self, obj):
        """Return initial users for comparison if applicable, respecting privacy settings"""
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user != obj.user:
            # Check if the viewed user has schedule comparison enabled
            if not obj.allow_schedule_comparison:
                return None
            
            return [
                {
                    'id': request.user.id,
                    'username': request.user.username,
                    'full_name': request.user.get_full_name(),
                    'profile_picture_url': request.user.userprofile.profile_picture.url if request.user.userprofile.profile_picture else None,
                },
                {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'full_name': obj.user.get_full_name(),
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


class UserSummarySerializer(serializers.ModelSerializer):
    """Small public user representation for search, mentions, and selectors."""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    school_email = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'full_name',
            'school_email', 'profile_picture_url', 'grade_level', 'is_teacher'
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_school_email(self, obj):
        profile = getattr(obj, 'userprofile', None)
        return obj.school_email if profile and profile.display_email else None
    
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


class UserSerializer(UserSummarySerializer):
    """Complete public profile representation."""
    userprofile = UserProfileSerializer(read_only=True)

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + ['date_joined', 'userprofile']


class FeedUserProfileSerializer(serializers.ModelSerializer):
    """Only the profile-picture field needed by legacy feed renderers."""
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['profile_picture']

    def get_profile_picture(self, obj):
        try:
            return obj.profile_picture.url if obj.profile_picture else None
        except (AttributeError, FileNotFoundError, ValueError):
            return None


class FeedUserSerializer(UserSummarySerializer):
    """Small author representation for post cards and feed responses."""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    userprofile = FeedUserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name',
                  'profile_picture_url', 'userprofile', 'is_teacher']

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_profile_picture_url(self, obj):
        try:
            profile = obj.userprofile
            return profile.profile_picture.url if profile.profile_picture else None
        except (AttributeError, FileNotFoundError, ValueError):
            return None


class PrivateUserProfileSerializer(UserProfileSerializer):
    """Owner-only profile settings and assets."""
    lunch_card = serializers.SerializerMethodField()
    has_wolfnet_password = serializers.SerializerMethodField()
    display_email = serializers.BooleanField(read_only=True)

    class Meta(UserProfileSerializer.Meta):
        fields = UserProfileSerializer.Meta.fields + [
            'lunch_card', 'has_wolfnet_password', 'display_email'
        ]

    def _should_hide_schedule(self, obj):
        return False

    def get_lunch_card(self, obj):
        try:
            return obj.lunch_card.url if obj.lunch_card else None
        except (AttributeError, FileNotFoundError, ValueError):
            return None

    def get_has_wolfnet_password(self, obj):
        return bool(obj.wolfnet_password)


class PrivateUserSerializer(UserSerializer):
    """Authenticated user's own account data. Never use for another user."""
    userprofile = PrivateUserProfileSerializer(read_only=True)
    school_email = serializers.EmailField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            'personal_email', 'phone_number', 'student_id'
        ]


class AnonymousAuthorSerializer(serializers.Serializer):
    """A fixed author projection that cannot expose fields from the real user."""
    id = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    userprofile = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    is_teacher = serializers.SerializerMethodField()
    is_anonymous = serializers.SerializerMethodField()

    def get_id(self, obj):
        return None

    def get_username(self, obj):
        return ''

    def get_first_name(self, obj):
        return 'Anonymous'

    def get_last_name(self, obj):
        return ''

    def get_full_name(self, obj):
        return 'Anonymous'

    def get_profile_picture_url(self, obj):
        return ANONYMOUS_PROFILE_PICTURE

    def get_userprofile(self, obj):
        return {'profile_picture': ANONYMOUS_PROFILE_PICTURE}

    def get_grade_level(self, obj):
        return None

    def get_is_teacher(self, obj):
        return False

    def get_is_anonymous(self, obj):
        return True


class UserScheduleSerializer(serializers.ModelSerializer):
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
        schedule = {}
        for block in USER_SCHEDULE_BLOCKS:
            course = getattr(obj, f'block_{block}', None)
            schedule[block] = {
                'course': course.name if course else None,
                'course_id': course.id if course else None,
            }
        return schedule
