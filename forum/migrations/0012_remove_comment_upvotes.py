# Generated by Django 4.2.16 on 2025-03-29 23:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0011_comment_parent_alter_comment_content'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='comment',
            name='upvotes',
        ),
    ]
