from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from forum.models import CommunityFollow, CommunityLunch, CommunitySubscription, User

_MISSING = object()


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


def _get_owned_active_community(user):
    if not user.is_active or not user.is_community_account:
        return None
    return user


def is_following_community(user, community):
    return bool(
        user.is_authenticated
        and user != community
        and community.is_community_account
        and community.is_active
        and CommunityFollow.objects.filter(user=user, community=community).exists()
    )


def _parse_lunch_date(value):
    if isinstance(value, date):
        lunch_date = value
    elif isinstance(value, str):
        try:
            lunch_date = date.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    return lunch_date if lunch_date >= timezone.localdate() else None


def cleanup_expired_community_lunches():
    """Delete lunch entries whose Vancouver calendar date has passed."""
    deleted, _ = CommunityLunch.objects.filter(date__lt=timezone.localdate()).delete()
    return deleted


def _normalize_location(value, required=True):
    location = str(value or '').strip()
    if (required and not location) or len(location) > 120:
        return None
    return location


def get_community_lunches_for_date(target_date, is_school_day):
    """Return active communities meeting on a school date, ready for serialization."""
    if not is_school_day or target_date < timezone.localdate():
        return CommunityLunch.objects.none()
    return CommunityLunch.objects.filter(
        date=target_date,
        community__is_community_account=True,
        community__is_active=True,
    ).select_related('community', 'community__userprofile')


def get_owned_community_lunches(user):
    community = _get_owned_active_community(user)
    if not community:
        return {'error': 'Only active community accounts can manage lunch dates.'}
    lunches = CommunityLunch.objects.filter(
        community=community,
        date__gte=timezone.localdate(),
    ).select_related(
        'community', 'community__userprofile'
    )
    return {'community': community, 'lunches': lunches}


@transaction.atomic
def add_community_lunch_service(user, date_value, location):
    community = _get_owned_active_community(user)
    if not community:
        return {'error': 'Only active community accounts can manage lunch dates.'}
    lunch_date = _parse_lunch_date(date_value)
    if not lunch_date:
        return {'error': 'Choose today or a future date in YYYY-MM-DD format.'}
    location = _normalize_location(location)
    if location is None:
        return {'error': 'Enter a location of 120 characters or fewer.'}
    lunch, created = CommunityLunch.objects.get_or_create(
        community=community,
        date=lunch_date,
        defaults={'location': location},
    )
    if not created and lunch.location != location:
        lunch.location = location
        lunch.save(update_fields=['location'])
    return {'lunch': lunch, 'created': created}


@transaction.atomic
def update_community_lunch_service(user, lunch_id, location=_MISSING, date_value=_MISSING):
    community = _get_owned_active_community(user)
    if not community:
        return {'error': 'Only active community accounts can manage lunch dates.'}
    lunch = CommunityLunch.objects.filter(id=lunch_id, community=community).first()
    if not lunch:
        return {'error': 'Lunch date not found.'}
    if location is _MISSING and date_value is _MISSING:
        return {'error': 'Provide a date or location to update.'}

    update_fields = []
    if location is not _MISSING:
        location = _normalize_location(location)
        if location is None:
            return {'error': 'Enter a location of 120 characters or fewer.'}
        if lunch.location != location:
            lunch.location = location
            update_fields.append('location')

    if date_value is not _MISSING:
        lunch_date = _parse_lunch_date(date_value)
        if not lunch_date:
            return {'error': 'Choose today or a future date in YYYY-MM-DD format.'}
        if lunch.date != lunch_date:
            if CommunityLunch.objects.filter(community=community, date=lunch_date).exclude(id=lunch.id).exists():
                return {'error': 'That lunch date is already listed.'}
            lunch.date = lunch_date
            update_fields.append('date')

    if update_fields:
        try:
            with transaction.atomic():
                lunch.save(update_fields=update_fields)
        except IntegrityError:
            if 'date' in update_fields:
                return {'error': 'That lunch date is already listed.'}
            raise
    return {'lunch': lunch}


@transaction.atomic
def delete_community_lunch_service(user, lunch_id):
    community = _get_owned_active_community(user)
    if not community:
        return {'error': 'Only active community accounts can manage lunch dates.'}
    deleted, _ = CommunityLunch.objects.filter(
        id=lunch_id,
        community=community,
    ).delete()
    if not deleted:
        return {'error': 'Lunch date not found.'}
    return {'deleted': True}


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
