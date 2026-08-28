from django.db import transaction
from django.utils import timezone

from forum.models import CommunityFollow, CommunitySubscription, User


def get_community_directory(user):
    """Return active communities and the viewer's follow/email state."""
    communities = User.objects.filter(
        is_community_account=True,
        is_active=True,
    ).select_related('userprofile').order_by('first_name', 'last_name', 'username')

    if not user.is_authenticated:
        return communities, set(), set()

    followed_ids = set(
        user.followed_communities.values_list('community_id', flat=True)
    )
    subscribed_ids = set(
        user.community_subscriptions.filter(is_active=True)
        .values_list('community_id', flat=True)
    )
    return communities, followed_ids, subscribed_ids


def _get_available_community(community_id):
    return User.objects.filter(
        id=community_id,
        is_community_account=True,
        is_active=True,
    ).first()


@transaction.atomic
def toggle_community_follow_service(user, community_id):
    community = _get_available_community(community_id)
    if not community:
        return {
            'error': 'Community account not available.',
            'error_code': 'community_unavailable',
        }
    if community == user:
        return {
            'error': 'A community account cannot follow itself.',
            'error_code': 'self_follow',
        }

    follow, created = CommunityFollow.objects.get_or_create(
        user=user,
        community=community,
    )
    if created:
        subscription, _ = CommunitySubscription.objects.get_or_create(
            user=user,
            community=community,
        )
        subscription.is_active = True
        subscription.unsubscribed_at = None
        subscription.save(update_fields=['is_active', 'unsubscribed_at'])
    else:
        follow.delete()
        CommunitySubscription.objects.filter(
            user=user,
            community=community,
            is_active=True,
        ).update(is_active=False, unsubscribed_at=timezone.now())

    return {
        'community': community,
        'following': created,
        'mailing_list_joined': created,
    }


@transaction.atomic
def toggle_community_subscription_service(user, community_id):
    community = _get_available_community(community_id)
    if not community:
        return {
            'error': 'Community account not available.',
            'error_code': 'community_unavailable',
        }
    if community == user:
        return {
            'error': 'A community account cannot subscribe to itself.',
            'error_code': 'self_subscription',
        }

    subscription, _ = CommunitySubscription.objects.get_or_create(
        user=user,
        community=community,
        defaults={'is_active': False},
    )
    if not subscription.is_active and not user.personal_email:
        return {
            'error': 'Add a personal email to your profile before enabling email updates.',
            'error_code': 'personal_email_required',
        }

    subscription.is_active = not subscription.is_active
    subscription.unsubscribed_at = None if subscription.is_active else timezone.now()
    subscription.save(update_fields=['is_active', 'unsubscribed_at'])
    return {
        'community': community,
        'subscribed': subscription.is_active,
    }
