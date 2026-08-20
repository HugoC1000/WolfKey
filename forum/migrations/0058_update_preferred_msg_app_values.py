from django.db import migrations, models


OLD_TO_CANONICAL_VALUES = {
    'insta': 'Instagram',
    'linkedin': 'LinkedIn',
    'snap': 'Snapchat',
    'email': 'Email',
    'discord': 'Discord',
}


def use_canonical_app_names(apps, schema_editor):
    UserProfile = apps.get_model('forum', 'UserProfile')
    for old_value, canonical_value in OLD_TO_CANONICAL_VALUES.items():
        UserProfile.objects.filter(preferred_msg_app=old_value).update(
            preferred_msg_app=canonical_value
        )


def use_legacy_app_names(apps, schema_editor):
    UserProfile = apps.get_model('forum', 'UserProfile')
    for old_value, canonical_value in OLD_TO_CANONICAL_VALUES.items():
        UserProfile.objects.filter(preferred_msg_app=canonical_value).update(
            preferred_msg_app=old_value
        )


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0057_userprofile_preferred_msg_app'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='preferred_msg_app',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Instagram', 'Instagram'),
                    ('LinkedIn', 'LinkedIn'),
                    ('Snapchat', 'Snapchat'),
                    ('Email', 'Email'),
                    ('Discord', 'Discord'),
                ],
                help_text='The app you prefer people to use when contacting you',
                max_length=9,
                null=True,
            ),
        ),
        migrations.RunPython(
            use_canonical_app_names,
            reverse_code=use_legacy_app_names,
        ),
    ]
