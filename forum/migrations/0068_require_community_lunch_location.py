from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0067_community_lunch_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='communitylunch',
            name='location',
            field=models.CharField(max_length=120),
        ),
    ]
