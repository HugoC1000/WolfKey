from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('forum', '0069_user_is_paid_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommentDownvote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='forum.comment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='forum.user')),
            ],
            options={'unique_together': {('comment', 'user')}},
        ),
    ]
