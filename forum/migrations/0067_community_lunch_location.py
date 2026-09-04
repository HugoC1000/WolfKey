from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0066_community_lunch'),
    ]

    operations = [
        migrations.AddField(
            model_name='communitylunch',
            name='location',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AlterField(
            model_name='communitylunch',
            name='date',
            field=models.DateField(db_index=True),
        ),
    ]
