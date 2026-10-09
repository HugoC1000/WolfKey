from django.db import migrations


def copy_moderator_group_to_profiles(apps, schema_editor):
    """Preserve existing group-based moderators before profiles become canonical."""
    UserProfile = apps.get_model('forum', 'UserProfile')
    UserProfile.objects.filter(user__groups__name='Moderators').update(is_moderator=True)


class Migration(migrations.Migration):
    dependencies = [
        ('forum', '0070_commentdownvote'),
    ]

    operations = [
        migrations.RunPython(copy_moderator_group_to_profiles, migrations.RunPython.noop),
    ]
