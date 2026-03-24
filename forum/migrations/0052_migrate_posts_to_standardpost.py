# Generated migration - Data migration to convert existing Posts to StandardPosts

from django.db import migrations, connection

def migrate_posts_to_standardpost(apps, schema_editor):
    """
    Convert all existing Post records to StandardPost records using raw SQL.
    This ensures all posts are properly typed as StandardPost subclass instances.
    """
    with connection.cursor() as cursor:
        # Insert all existing Posts that aren't already StandardPost or Poll into StandardPost table
        cursor.execute("""
            INSERT INTO forum_standardpost (post_ptr_id)
            SELECT id FROM forum_post
            WHERE content IS NOT NULL
            AND id NOT IN (SELECT COALESCE(post_ptr_id, 0) FROM forum_standardpost)
            AND id NOT IN (SELECT COALESCE(post_ptr_id, 0) FROM forum_poll)
            ON CONFLICT DO NOTHING;
        """)


def reverse_migrate(apps, schema_editor):
    """
    Reverse migration - delete StandardPost entries but keep the base Post records.
    """
    StandardPost = apps.get_model('forum', 'StandardPost')
    StandardPost.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0051_poll_polloption_standardpost_alter_post_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_posts_to_standardpost, reverse_migrate),
    ]
