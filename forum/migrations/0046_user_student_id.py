# Generated migration for adding student_id field
from django.db import migrations, models


def populate_student_id(apps, schema_editor):
    """
    Populate student_id from school_email for all existing users.
    Extracts only the numeric digits from the part before @ in the school_email.
    Example: abc12345@wpga.ca -> 12345
    """
    import re
    User = apps.get_model('forum', 'User')
    for user in User.objects.all():
        if user.school_email:
            email_prefix = user.school_email.split('@')[0]
            # Extract only numeric characters
            numbers_only = re.sub(r'[^0-9]', '', email_prefix)
            if numbers_only:
                user.student_id = numbers_only
                user.save(update_fields=['student_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0045_populate_last_activity_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='student_id',
            field=models.CharField(blank=True, help_text='Student ID extracted from school email', max_length=20, null=True),
        ),
        migrations.RunPython(populate_student_id, reverse_code=migrations.RunPython.noop),
    ]
