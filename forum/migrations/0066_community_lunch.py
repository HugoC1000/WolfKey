# Generated manually for the date-specific community lunch schedule.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0065_remove_user_community_paid_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityLunch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('community', models.ForeignKey(limit_choices_to={'is_community_account': True}, on_delete=django.db.models.deletion.CASCADE, related_name='community_lunches', to='forum.user')),
            ],
            options={
                'ordering': ['date', 'community__first_name', 'community__last_name', 'community__username'],
            },
        ),
        migrations.AddConstraint(
            model_name='communitylunch',
            constraint=models.UniqueConstraint(fields=('community', 'date'), name='unique_community_lunch_date'),
        ),
    ]
