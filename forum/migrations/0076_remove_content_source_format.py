from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('forum', '0075_markdown_content')]

    operations = [
        migrations.RemoveField(model_name='post', name='content_source_format'),
        migrations.RemoveField(model_name='solution', name='content_source_format'),
        migrations.RemoveField(model_name='comment', name='content_source_format'),
    ]
