# Generated migration to add post_type field to Post model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0052_migrate_posts_to_standardpost'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='post_type',
            field=models.CharField(
                choices=[('standard', 'Standard Post'), ('poll', 'Poll')],
                default='standard',
                max_length=20
            ),
        ),
    ]
