# Generated by Django 4.2.16 on 2025-03-12 01:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0009_updateannouncement_userupdateview'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='accepted_solution',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='accepted_for', to='forum.solution'),
        ),
        migrations.AddField(
            model_name='post',
            name='solved',
            field=models.BooleanField(default=False),
        ),
    ]
