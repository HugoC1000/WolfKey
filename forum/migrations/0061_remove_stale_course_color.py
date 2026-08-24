from django.db import migrations


def remove_stale_course_color(apps, schema_editor):
    """Remove a legacy database-only column without breaking clean installs."""
    table_name = 'forum_course'
    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name,
            )
        }

    if 'color' not in columns:
        return

    quoted_table = schema_editor.quote_name(table_name)
    quoted_column = schema_editor.quote_name('color')
    schema_editor.execute(f'ALTER TABLE {quoted_table} DROP COLUMN {quoted_column}')


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0060_normalize_course_categories'),
    ]

    operations = [
        migrations.RunPython(remove_stale_course_color, migrations.RunPython.noop),
    ]
