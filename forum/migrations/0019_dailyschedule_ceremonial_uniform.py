# Generated by Django 4.2.16 on 2025-04-20 19:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0018_dailyschedule_block_1_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyschedule',
            name='ceremonial_uniform',
            field=models.BooleanField(null=True),
        ),
    ]
