from rest_framework import serializers
from forum.models import User, UserProfile, Course
from django.conf import settings
from django.db.models import Count

ANONYMOUS_PROFILE_PICTURE = f"{settings.MEDIA_URL}profile_pictures/default.png"
USER_SCHEDULE_BLOCKS = ('1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E')


def safe_file_url(file_field, fallback=None):
    """Return a storage-backed file URL without leaking storage exceptions."""
    try:
        return file_field.url if file_field else fallback
    except (AttributeError, FileNotFoundError, ValueError):
        return fallback


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
    grade_level = serializers.IntegerField(read_only=True)
    allow_schedule_comparison = serializers.BooleanField(read_only=True)
    profile_picture = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    recent_posts = serializers.SerializerMethodField()
    can_compare = serializers.SerializerMethodField()
    initial_users = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    instagram_url = serializers.SerializerMethodField()
    snapchat_url = serializers.SerializerMethodField()
    linkedin_url = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'bio', 'points', 'is_moderator', 'created_at', 'updated_at',
            'background_hue', 'profile_picture',
            'grade_level', 'allow_schedule_comparison',
            'stats', 'courses', 'recent_posts',
            'can_compare', 'initial_users', 'schedule',
            'instagram_url', 'snapchat_url', 'linkedin_url',
            'preferred_msg_app'
        ]
    

    def get_profile_picture(self, obj):
        """Return profile picture URL"""
        return safe_file_url(obj.profile_picture)
    
    def _should_hide_schedule(self, obj):
        """Check if schedule fields should be hidden based on privacy settings"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return True
        if request.user == obj.user:
            return False
        return not obj.allow_schedule_comparison
    
    def get_schedule(self, obj):
        """Return the canonical schedule shape while enforcing profile privacy."""
        if self._should_hide_schedule(obj):
            return None
        return UserScheduleSerializer(obj, context=self.context).data['schedule']
    
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
        """Return the user's experienced and help-needed courses."""
        from forum.models import UserCourseExperience, UserCourseHelp
        
        experienced_courses = UserCourseExperience.objects.filter(
            user=obj.user
        ).select_related('course')
        help_needed_courses = UserCourseHelp.objects.filter(
            user=obj.user,
            active=True,
        ).select_related('course')
        
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
                    'profile_picture_url': safe_file_url(request.user.userprofile.profile_picture),
                },
                {
                    'id': obj.user.id,
                    'username': obj.user.username,
                    'full_name': obj.user.get_full_name(),
                    'profile_picture_url': safe_file_url(obj.profile_picture),
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


class FeedUserProfileSerializer(serializers.ModelSerializer):
    """Compact public profile fields embedded with user summaries and authors."""
    profile_picture = serializers.SerializerMethodField()
    instagram_url = serializers.SerializerMethodField()
    snapchat_url = serializers.SerializerMethodField()
    linkedin_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'profile_picture', 'preferred_msg_app',
            'instagram_url', 'snapchat_url', 'linkedin_url',
        ]

    def get_profile_picture(self, obj):
        return safe_file_url(obj.profile_picture)

    def get_instagram_url(self, obj):
        return obj.get_instagram_url()

    def get_snapchat_url(self, obj):
        return obj.get_snapchat_url()

    def get_linkedin_url(self, obj):
        return obj.get_linkedin_url()


class UserSummarySerializer(serializers.ModelSerializer):
    """Small public user representation for search, mentions, and selectors."""
    full_name = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    grade_level = serializers.SerializerMethodField()
    school_email = serializers.SerializerMethodField()
    userprofile = FeedUserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'full_name',
            'school_email', 'profile_picture_url', 'grade_level', 'is_teacher',
            'is_community_account', 'userprofile',
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_school_email(self, obj):
        profile = getattr(obj, 'userprofile', None)
        return obj.school_email if profile and profile.display_email else None
    
    def get_profile_picture_url(self, obj):
        """Return profile picture URL"""
        profile = getattr(obj, 'userprofile', None)
        return safe_file_url(profile.profile_picture if profile else None)

    def get_grade_level(self, obj):
        try:
            return obj.userprofile.grade_level if hasattr(obj, 'userprofile') else None
        except Exception:
            return None


class UserSerializer(UserSummarySerializer):
    """Complete public profile representation."""
    userprofile = UserProfileSerializer(read_only=True)
    is_following_community = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + ['date_joined', 'is_active', 'is_following_community']

    def get_is_following_community(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        from forum.services.community_services import is_following_community
        return is_following_community(request.user, obj)


class FeedUserSerializer(UserSummarySerializer):
    """Small author representation for post cards and feed responses."""
    class Meta(UserSummarySerializer.Meta):
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name',
                  'profile_picture_url', 'userprofile', 'is_teacher', 'is_community_account']


class CommunityAccountSerializer(serializers.ModelSerializer):
    """Public Community-directory data plus viewer-specific membership state."""
    full_name = serializers.SerializerMethodField()
    bio = serializers.CharField(source='userprofile.bio', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    email_updates_enabled = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'bio', 'profile_picture_url',
            'is_following', 'email_updates_enabled',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_profile_picture_url(self, obj):
        return safe_file_url(obj.userprofile.profile_picture)

    def get_is_following(self, obj):
        return obj.id in self.context.get('followed_community_ids', set())

    def get_email_updates_enabled(self, obj):
        return obj.id in self.context.get('subscribed_community_ids', set())


class PrivateUserProfileSerializer(UserProfileSerializer):
    """Owner-only profile settings and assets."""
    lunch_card = serializers.SerializerMethodField()
    display_email = serializers.BooleanField(read_only=True)

    class Meta(UserProfileSerializer.Meta):
        fields = UserProfileSerializer.Meta.fields + [
            'lunch_card', 'display_email'
        ]

    def _should_hide_schedule(self, obj):
        return False

    def get_lunch_card(self, obj):
        return safe_file_url(obj.lunch_card)


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
        return safe_file_url(obj.profile_picture)
    
    def get_schedule(self, obj):
        schedule = {}
        for block in USER_SCHEDULE_BLOCKS:
            course = getattr(obj, f'block_{block}', None)
            schedule[block] = {
                'course': course.name if course else None,
                'course_id': course.id if course else None,
            }
        return schedule


class CourseRosterStudentSerializer(serializers.ModelSerializer):
    """Public, minimal identity data for a course roster entry."""
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['username', 'full_name', 'initials', 'profile_picture_url']

    def get_full_name(self, obj):
        return obj.user.get_full_name().strip() or obj.user.username

    def get_initials(self, obj):
        return ''.join(part[0] for part in self.get_full_name(obj).split()[:2]).upper()

    def get_profile_picture_url(self, obj):
        return safe_file_url(obj.profile_picture)
