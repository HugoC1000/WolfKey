from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from .models import Post, File, UserProfile, SavedPost, Solution, Course, CourseAlias, User, UserCourseExperience, UserCourseHelp,UpdateAnnouncement, DailySchedule, SavedSolution, FollowedPost, GradebookSnapshot


# Register your models here.
admin.site.register(Post)
admin.site.register(File)
admin.site.register(SavedPost)
admin.site.register(FollowedPost)
admin.site.register(Solution)
admin.site.register(SavedSolution)
admin.site.register(UserCourseExperience)
admin.site.register(UserCourseHelp)
admin.site.register(UpdateAnnouncement)
admin.site.register(DailySchedule)
admin.site.register(GradebookSnapshot)

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('bio', 'profile_picture', 'background_hue', 'points', 'is_moderator', 'wolfnet_password', 'expo_push_token', 'grade_level')
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

class UserAdmin(admin.ModelAdmin):
    inlines = [UserProfileInline]
    list_display = ('school_email', 'first_name', 'last_name', 'is_teacher', 'is_staff', 'is_superuser')
    search_fields = ('school_email', 'first_name', 'last_name')
    ordering = ('school_email',)
    
    fieldsets = (
        (None, {
            'fields': ('school_email', 'password')
        }),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'personal_email', 'phone_number', 'is_teacher')
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

class CourseAliasInline(admin.TabularInline):
    model = CourseAlias
    extra = 1  # Number of empty aliases to display by default

class CourseAdmin(admin.ModelAdmin):
    inlines = [CourseAliasInline]

admin.site.register(Course, CourseAdmin)