# Generated by Django 4.2.16 on 2024-12-28 00:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0007_post_search_vector_post_tags'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='post',
            name='search_vector',
        ),
    ]
