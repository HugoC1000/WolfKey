from rest_framework import serializers
from forum.models import User, UserProfile, Course
from django.conf import settings

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
        from forum.models import Post
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

    def get_last_name(self, obj):
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
