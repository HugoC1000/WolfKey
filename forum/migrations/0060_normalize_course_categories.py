from django.db import migrations, models


CATEGORY_RENAMES = {
    'Arts': 'Art',
    'Fine Arts': 'Art',
    'Langauge': 'Language',
    'Physical Education': 'PE',
    'Sciences': 'Science',
    'Social Studes': 'Social Studies',
    'Technology': 'Information Technology',
    'trust': 'Misc',
}


def normalize_categories(apps, schema_editor):
    Course = apps.get_model('forum', 'Course')
    for old_value, new_value in CATEGORY_RENAMES.items():
        Course.objects.filter(category=old_value).update(category=new_value)


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0059_courseteacher_courseteachervote_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_categories, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='course',
            name='category',
            field=models.CharField(
                choices=[
                    ('Art', 'Art'), ('Biology', 'Biology'), ('Chemistry', 'Chemistry'),
                    ('Drama', 'Drama'), ('Environmental Science', 'Environmental Science'), ('English', 'English'),
                    ('French', 'French'), ('Humanities', 'Humanities'),
                    ('Information Technology', 'Information Technology'),
                    ('Language', 'Language'), ('Mandarin', 'Mandarin'), ('Design', 'Design'), ('Math', 'Math'),
                    ('Misc', 'Misc'), ('Music', 'Music'), ('PE', 'Physical Education'), ('Physics', 'Physics'),
                    ('Science', 'Science'), ('Social Studies', 'Social Studies'), ('Spanish', 'Spanish'),
                    ('Study Hall', 'Study Hall'),
                ],
                default='Misc',
                max_length=100,
            ),
        ),
    ]
