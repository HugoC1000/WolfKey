import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .user import User, UserProfile
from .post import Post
from .solution import Solution, Comment

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved"""
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)


@receiver(pre_delete, sender=Solution)
def delete_solution_files(sender, instance, **kwargs):
    """Delete files referenced in solution content before deleting the solution"""
    if instance.content:
        from forum.services.utils import extract_and_delete_files_from_content
        try:
            extract_and_delete_files_from_content(instance.content)
        except Exception as e:
            logger.error(f"Error deleting files for solution {instance.id}: {str(e)}")


@receiver(pre_delete, sender=Comment)
def delete_comment_files(sender, instance, **kwargs):
    """Delete files referenced in comment content before deleting the comment"""
    if instance.content:
        from forum.services.utils import extract_and_delete_files_from_content
        try:
            extract_and_delete_files_from_content(instance.content)
        except Exception as e:
            logger.error(f"Error deleting files for comment {instance.id}: {str(e)}")


@receiver(pre_delete, sender=Post)
def delete_post_files(sender, instance, **kwargs):
    """Delete files referenced in post content before deleting the post"""
    if instance.content:
        from forum.services.utils import extract_and_delete_files_from_content
        try:
            extract_and_delete_files_from_content(instance.content)
        except Exception as e:
            logger.error(f"Error deleting files for post {instance.id}: {str(e)}")
