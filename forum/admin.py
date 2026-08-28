from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.utils.html import format_html
from .models import Post, StandardPost, Poll, PollOption, PollVote, File, UserProfile, Solution, Course, CourseAlias, CourseTeacher, User, UserCourseExperience, UserCourseHelp,UpdateAnnouncement, DailySchedule, FollowedPost, GradebookSnapshot, VolunteerPinMilestone, VolunteerResource, CommunityFollow, CommunitySubscription


class StandardPostInline(admin.StackedInline):
    model = StandardPost
    extra = 0
    can_delete = False
    verbose_name_plural = 'Standard Post Details'


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 1
    fields = ('text',)


class PollAdmin(admin.ModelAdmin):
    inlines = [PollOptionInline]
    list_display = ('title', 'author', 'scope', 'is_pinned_in_community', 'created_at', 'is_public_voting', 'allow_multiple_choice')
    list_filter = ('scope', 'is_pinned_in_community', 'is_public_voting', 'allow_multiple_choice', 'created_at')
    search_fields = ('title', 'author__school_email', 'author__first_name', 'author__last_name')
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Post Content', {
            'fields': ('title', 'content', 'author')
        }),
        ('Poll Settings', {
            'fields': ('is_public_voting', 'allow_multiple_choice')
        }),
        ('Post Settings', {
            'fields': ('scope', 'is_pinned_in_community', 'is_anonymous', 'allow_teacher', 'solved')
        }),
        ('Metadata', {
            'fields': ('created_at', 'last_activity_at', 'views', 'courses', 'accepted_solution'),
            'classes': ('collapse',),
        }),
    )


class PollInline(admin.StackedInline):
    model = Poll
    extra = 0
    can_delete = False
    verbose_name_plural = 'Poll Details'
    fields = ('is_public_voting', 'allow_multiple_choice')


class PostAdmin(admin.ModelAdmin):
    inlines = [StandardPostInline, PollInline]
    list_display = ('title', 'author', 'scope', 'is_pinned_in_community', 'created_at', 'get_post_type')
    list_filter = ('scope', 'is_pinned_in_community', 'created_at', 'is_anonymous', 'allow_teacher')
    search_fields = ('title', 'author__school_email', 'author__first_name', 'author__last_name')
    readonly_fields = ('created_at', 'search_vector')
    
    fieldsets = (
        ('Post Content', {
            'fields': ('title', 'content', 'author')
        }),
        ('Post Settings', {
            'fields': ('scope', 'is_pinned_in_community', 'is_anonymous', 'allow_teacher', 'solved')
        }),
        ('Metadata', {
            'fields': ('created_at', 'last_activity_at', 'views', 'courses', 'accepted_solution'),
            'classes': ('collapse',),
        }),
    )
    
    def get_post_type(self, obj):
        """Display the post type based on which subclass exists"""
        if hasattr(obj, 'poll'):
            return 'Poll'
        elif hasattr(obj, 'standardpost'):
            return 'Standard Post'
        return 'Base Post'
    get_post_type.short_description = 'Type'


# Register your models here.
admin.site.register(Post, PostAdmin)
admin.site.register(Poll, PollAdmin)
admin.site.register(File)
admin.site.register(FollowedPost)
admin.site.register(Solution)
admin.site.register(UserCourseExperience)
admin.site.register(UserCourseHelp)
admin.site.register(UpdateAnnouncement)
admin.site.register(DailySchedule)
admin.site.register(GradebookSnapshot)
admin.site.register(VolunteerPinMilestone)
admin.site.register(VolunteerResource)

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    readonly_fields = ('lunch_card_url', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('bio', 'profile_picture', 'lunch_card_url', 'background_hue', 'points', 'is_moderator', 'wolfnet_password', 'expo_push_token', 'grade_level')
        }),
        ('Course Blocks', {
            'fields': (
                ('block_1A', 'block_1B', 'block_1D', 'block_1E'),
                ('block_2A', 'block_2B', 'block_2C', 'block_2D', 'block_2E'),
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def lunch_card_url(self, obj):
        if obj and obj.lunch_card:
            return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', obj.lunch_card.url, obj.lunch_card.url)
        return '-'

    lunch_card_url.short_description = 'Lunch card URL'

class UserAdmin(admin.ModelAdmin):
    inlines = [UserProfileInline]
    list_display = ('school_email', 'first_name', 'last_name', 'is_community_account', 'is_active', 'is_teacher', 'volunteer_coordinator', 'is_staff', 'is_superuser')
    search_fields = ('school_email', 'first_name', 'last_name')
    ordering = ('school_email',)
    
    fieldsets = (
        (None, {
            'fields': ('school_email', 'password')
        }),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'personal_email', 'student_id', 'volunteer_coordinator', 'phone_number', 'is_teacher', 'is_community_account')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = ('last_login', 'date_joined')

    def get_inline_instances(self, request, obj=None):
        # Only show profile inline for existing users
        if not obj:
            return []
        return super().get_inline_instances(request, obj)

admin.site.register(User, UserAdmin)
admin.site.register(CommunityFollow)
admin.site.register(CommunitySubscription)

class CourseAliasInline(admin.TabularInline):
    model = CourseAlias
    extra = 1


class CourseTeacherInline(admin.TabularInline):
    model = CourseTeacher
    extra = 0
    fields = ('block', 'teacher_name')


class CourseAdmin(admin.ModelAdmin):
    inlines = [CourseAliasInline, CourseTeacherInline]
    list_display = ('name', 'category', 'max_grade', 'display_blocks', 'display_aliases')
    list_editable = ('category', 'max_grade')
    list_filter = ('category', 'max_grade', 'blocks')
    search_fields = ('name', 'aliases__name')
    ordering = ('name',)
    filter_horizontal = ('blocks',)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('blocks', 'aliases')

    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty_first_page=True):
        """Keep every matching course on the same admin changelist page."""
        return super().get_paginator(
            request,
            queryset,
            max(queryset.count(), 1),
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
        )

    @admin.display(description='Blocks')
    def display_blocks(self, obj):
        return ', '.join(block.code for block in sorted(obj.blocks.all(), key=lambda block: block.code)) or '—'

    @admin.display(description='Aliases')
    def display_aliases(self, obj):
        return ', '.join(alias.name for alias in sorted(obj.aliases.all(), key=lambda alias: alias.name)) or '—'

admin.site.register(Course, CourseAdmin)
admin.site.register(CourseTeacher)
