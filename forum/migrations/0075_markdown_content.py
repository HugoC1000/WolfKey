from django.db import migrations, models
from django.contrib.postgres.search import SearchVector


def backfill_markdown(apps, schema_editor):
    from forum.services.content_format import editorjs_to_markdown

    for model_name in ('Post', 'Solution', 'Comment'):
        model = apps.get_model('forum', model_name)
        batch = []
        for item in model.objects.using(schema_editor.connection.alias).all().iterator(chunk_size=500):
            item.content_markdown = editorjs_to_markdown(item.content)
            batch.append(item)
            if len(batch) == 500:
                model.objects.using(schema_editor.connection.alias).bulk_update(batch, ['content_markdown'])
                batch.clear()
        if batch:
            model.objects.using(schema_editor.connection.alias).bulk_update(batch, ['content_markdown'])
        if model_name == 'Post':
            model.objects.using(schema_editor.connection.alias).update(
                search_vector=(
                    SearchVector('title', weight='A') +
                    SearchVector('content_markdown', weight='B')
                )
            )


class Migration(migrations.Migration):
    dependencies = [('forum', '0074_dailyschedule_calendar_verified')]

    operations = [
        migrations.AddField(
            model_name='post', name='content_markdown',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='post', name='content_source_format',
            field=models.CharField(
                choices=[('editorjs', 'Editor.js'), ('markdown', 'Markdown')],
                default='editorjs', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='solution', name='content_markdown',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='solution', name='content_source_format',
            field=models.CharField(
                choices=[('editorjs', 'Editor.js'), ('markdown', 'Markdown')],
                default='editorjs', max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='comment', name='content_markdown',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='comment', name='content_source_format',
            field=models.CharField(
                choices=[('editorjs', 'Editor.js'), ('markdown', 'Markdown')],
                default='editorjs', max_length=10,
            ),
        ),
        migrations.RunPython(backfill_markdown, migrations.RunPython.noop),
    ]
