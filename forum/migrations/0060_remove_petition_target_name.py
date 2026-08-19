from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('forum', '0059_petition'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='petition',
            name='target_name',
        ),
    ]
