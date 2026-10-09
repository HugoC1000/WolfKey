from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('forum', '0073_remove_userprofile_wolfnet_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyschedule',
            name='calendar_verified',
            field=models.BooleanField(default=False),
        ),
    ]
