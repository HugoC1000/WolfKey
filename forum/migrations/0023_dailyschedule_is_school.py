# Generated by Django 4.2.16 on 2025-04-27 19:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0022_alter_userprofile_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyschedule',
            name='is_school',
            field=models.BooleanField(null=True),
        ),
    ]
