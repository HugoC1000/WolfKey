"""Lifecycle safeguards that must also run for admin actions and cascades.

Feature behavior belongs in ``forum.services`` so its execution is visible from
the calling view or API endpoint. These receivers are reserved for invariants
that must hold whenever a model is saved or deleted through any code path.
"""

import logging

from django.db.models.signals import post_migrate, post_save, pre_delete
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from .models import Comment, Post, Solution, User, UserProfile

logger = logging.getLogger(__name__)


@receiver(post_migrate, dispatch_uid='forum_create_legacy_app_update_post')
def create_legacy_app_update_post(sender, **kwargs):
    """Seed one empty admin-authored post for clients using the legacy feed API."""
    if sender.label != 'forum':
        return

    _ensure_legacy_app_update_post()


def _ensure_legacy_app_update_post():
    from forum.services.legacy_app_update import get_legacy_app_update_post

    if get_legacy_app_update_post() is None:
        logger.info('Skipping legacy app update post: no superuser exists yet.')


@receiver(post_save, sender=User, dispatch_uid='forum_create_update_post_for_new_admin')
def create_update_post_when_admin_is_created(sender, instance, created, **kwargs):
    """Also seed the post when a deployment creates its first admin after migration."""
    if created and instance.is_superuser:
        _ensure_legacy_app_update_post()


@receiver(post_save, sender=User)
def maintain_user_account_invariants(sender, instance, created, **kwargs):
    """Ensure every user has a profile and inactive users have no API token."""
    UserProfile.objects.get_or_create(user=instance)
    if not instance.is_active:
        Token.objects.filter(user=instance).delete()


def _delete_content_files(instance):
    """Best-effort cleanup used by all content deletion receivers."""
    if not instance.content and not instance.content_markdown:
        return

    from forum.services.utils import extract_and_delete_files_from_content

    try:
        extract_and_delete_files_from_content(instance.content_markdown or instance.content)
    except Exception:
        logger.exception("Failed to delete files for %s %s", type(instance).__name__, instance.id)


@receiver(pre_delete, sender=Post)
def delete_post_files(sender, instance, **kwargs):
    _delete_content_files(instance)


@receiver(pre_delete, sender=Solution)
def delete_solution_files(sender, instance, **kwargs):
    _delete_content_files(instance)


@receiver(pre_delete, sender=Comment)
def delete_comment_files(sender, instance, **kwargs):
    _delete_content_files(instance)
