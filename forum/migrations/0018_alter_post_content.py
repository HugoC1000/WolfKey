# Generated by Django 4.2.16 on 2025-03-03 05:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0017_solutiondownvote'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='content',
            field=models.JSONField(),
        ),
    ]
