# Generated by Django 4.2.16 on 2025-04-20 02:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0017_alter_dailyschedule_block_1_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyschedule',
            name='block_1_time',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='dailyschedule',
            name='block_2_time',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='dailyschedule',
            name='block_3_time',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='dailyschedule',
            name='block_4_time',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='dailyschedule',
            name='block_5_time',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
