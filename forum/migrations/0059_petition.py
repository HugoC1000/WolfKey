import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0058_update_preferred_msg_app_values'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='post_type',
            field=models.CharField(
                choices=[
                    ('standard', 'Standard Post'),
                    ('poll', 'Poll'),
                    ('petition', 'Petition'),
                ],
                default='standard',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='Petition',
            fields=[
                (
                    'poll_ptr',
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to='forum.poll',
                    ),
                ),
                ('target_name', models.CharField(max_length=200)),
                (
                    'support_goal',
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
            ],
            options={
                'verbose_name': 'Petition',
                'verbose_name_plural': 'Petitions',
                'constraints': [
                    models.CheckConstraint(
                        check=(
                            models.Q(('support_goal__isnull', True))
                            | models.Q(('support_goal__gte', 1))
                        ),
                        name='petition_support_goal_positive',
                    ),
                ],
            },
            bases=('forum.poll',),
        ),
    ]
