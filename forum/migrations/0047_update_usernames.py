# Generated migration to update usernames to [firstname]-[lastname]-[num] format

from django.db import migrations
import re


def update_usernames(apps, schema_editor):
    """
    Update all existing usernames to the new format: [firstname]-[lastname]-[num].
    
    This migration updates existing users' usernames while handling duplicates
    by appending a number to ensure uniqueness. Sanitizes names by:
    - Converting to lowercase
    - Replacing spaces/underscores with hyphens
    - Removing special characters (keeping only alphanumeric and hyphens)
    - Collapsing multiple hyphens and removing leading/trailing hyphens
    """
    User = apps.get_model('forum', 'User')
    import uuid
    
    # Dictionary to track base usernames and their counts
    username_counts = {}
    
    for user in User.objects.all().order_by('id'):
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        
        # Normalize names: lowercase, replace spaces/underscores with hyphens
        first_clean = first_name.lower().strip()
        last_clean = last_name.lower().strip()
        
        # Replace spaces and underscores with hyphens
        first_clean = re.sub(r'[\s_]+', '-', first_clean)
        last_clean = re.sub(r'[\s_]+', '-', last_clean)
        
        # Remove all other special characters, keep only alphanumeric and hyphens
        first_clean = re.sub(r'[^a-z0-9-]', '', first_clean)
        last_clean = re.sub(r'[^a-z0-9-]', '', last_clean)
        
        # Remove leading/trailing hyphens and collapse multiple consecutive hyphens
        first_clean = re.sub(r'-+', '-', first_clean).strip('-')
        last_clean = re.sub(r'-+', '-', last_clean).strip('-')
        
        # Determine base username
        if not first_clean and not last_clean:
            # Fallback to UUID if both names are empty after sanitization
            base_username = f"user-{str(uuid.uuid4())[:8]}"
        elif not last_clean:
            base_username = first_clean
        elif not first_clean:
            base_username = last_clean
        else:
            base_username = f"{first_clean}-{last_clean}"
        
        # Increment the counter for this base username
        if base_username not in username_counts:
            username_counts[base_username] = 1
        else:
            username_counts[base_username] += 1
        
        new_username = f"{base_username}-{username_counts[base_username]}"
        
        # Check if the new username is different from the current one
        if user.username != new_username:
            # Ensure the new username doesn't already exist
            counter = username_counts[base_username]
            while User.objects.filter(username=new_username).exclude(id=user.id).exists():
                counter += 1
                new_username = f"{base_username}-{counter}"
            
            user.username = new_username
            user.save(update_fields=['username'])


def reverse_usernames(apps, schema_editor):
    """
    This migration cannot be safely reversed as we don't store the old UUIDs.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0046_user_student_id'),
    ]

    operations = [
        migrations.RunPython(update_usernames, reverse_code=reverse_usernames),
    ]
