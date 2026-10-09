from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0072_remove_update_announcements'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='wolfnet_password',
        ),
    ]
