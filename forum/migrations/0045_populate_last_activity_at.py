# Generated manually to populate last_activity_at with created_at for existing posts

from django.db import migrations
from django.db.models import F


def populate_last_activity_at(apps, schema_editor):
    """Set last_activity_at to created_at for all existing posts"""
    Post = apps.get_model('forum', 'Post')
    Post.objects.filter(last_activity_at__isnull=True).update(last_activity_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0044_post_last_activity_at'),
    ]

    operations = [
        migrations.RunPython(populate_last_activity_at, migrations.RunPython.noop),
    ]
