from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0064_backfill_community_post_scope'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='community_paid_at',
        ),
    ]
