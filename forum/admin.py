from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from .models import Post, Tag, File, UserProfile, SavedPost, Solution

admin.site.register(Post)
admin.site.register(Tag)
admin.site.register(File)
admin.site.register(UserProfile)
admin.site.register(Solution)
admin.site.register(SavedPost)

def create_moderator_group():
    moderator_group, created = Group.objects.get_or_create(name='Moderators')
    if created:
        permissions = [
            'can_delete_posts',
            'can_edit_posts',
            'can_ban_users',
            'can_pin_posts'
        ]
        for perm in permissions:
            moderator_group.permissions.add(Permission.objects.get(codename=perm))