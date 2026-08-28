from django.db import migrations


def backfill_community_post_scope(apps, schema_editor):
    Post = apps.get_model('forum', 'Post')
    community_posts = Post.objects.filter(author__is_community_account=True)
    community_post_ids = list(community_posts.values_list('id', flat=True))
    community_posts.update(
        scope='community',
        is_anonymous=False,
        allow_teacher=True,
    )
    Post.courses.through.objects.filter(post_id__in=community_post_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0063_community_accounts'),
    ]

    operations = [
        migrations.RunPython(backfill_community_post_scope, migrations.RunPython.noop),
    ]
