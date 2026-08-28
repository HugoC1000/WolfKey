# Generated manually because the local Django runtime is missing cryptography.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0062_remove_courseteacher_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='community_paid_at',
            field=models.DateTimeField(blank=True, help_text='When the in-person community account fee was collected.', null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='is_community_account',
            field=models.BooleanField(default=False, help_text='Allows this account to publish on the Community page.'),
        ),
        migrations.AddField(
            model_name='post',
            name='scope',
            field=models.CharField(choices=[('school', 'School'), ('community', 'Community')], default='school', max_length=20),
        ),
        migrations.AddField(
            model_name='post',
            name='is_pinned_in_community',
            field=models.BooleanField(default=False, help_text='Show this community post before unpinned posts on the Community page only.'),
        ),
        migrations.CreateModel(
            name='CommunityFollow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('followed_at', models.DateTimeField(auto_now_add=True)),
                ('community', models.ForeignKey(limit_choices_to={'is_community_account': True}, on_delete=django.db.models.deletion.CASCADE, related_name='community_followers', to='forum.user')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='followed_communities', to='forum.user')),
            ],
            options={'unique_together': {('user', 'community')}},
        ),
        migrations.CreateModel(
            name='CommunitySubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True)),
                ('subscribed_at', models.DateTimeField(auto_now_add=True)),
                ('unsubscribed_at', models.DateTimeField(blank=True, null=True)),
                ('community', models.ForeignKey(limit_choices_to={'is_community_account': True}, on_delete=django.db.models.deletion.CASCADE, related_name='mailing_list_subscribers', to='forum.user')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_subscriptions', to='forum.user')),
            ],
            options={'unique_together': {('user', 'community')}},
        ),
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('post', 'New Post'), ('solution', 'New Solution'), ('comment', 'New Comment'), ('reply', 'New Reply'), ('grade_update', 'Grade Update'), ('edit', 'Post Edit'), ('mention', 'Mention'), ('channel', 'Channel Mention'), ('everyone', 'Everyone Mention'), ('community', 'Community Post')], max_length=20),
        ),
    ]
