"""Small, shared event recorder and database-side daily aggregation."""
import logging
from contextvars import ContextVar
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from forum.models.analytics import AnalyticsEvent

logger = logging.getLogger(__name__)
VANCOUVER = ZoneInfo('America/Vancouver')
request_platform = ContextVar('analytics_platform', default='web')
SCREENS = {
    'home', 'explore', 'community', 'post_detail', 'create_post', 'edit_post',
    'edit_solution', 'profile', 'edit_profile', 'search', 'match', 'volunteer',
    'notifications', 'subjects', 'course', 'atlas', 'bookmarks', 'my_posts',
    'settings', 'lunch_card', 'schedule', 'about', 'privacy',
}
CLIENT_EVENTS = {'screen_open', 'match_open', 'profile_search', 'volunteer_open'}
FEATURE_SCREENS = {
    'match_open': {'match', 'profile'},
    'profile_search': {'search', 'explore', 'match', 'atlas'},
    'volunteer_open': {'volunteer'},
}
WEB_SCREENS = {
    'all_posts': 'home', 'for_you': 'home', 'community': 'community',
    'post_detail': 'post_detail', 'create_post': 'create_post', 'edit_post': 'edit_post',
    'edit_solution': 'edit_solution', 'my_profile': 'profile', 'profile': 'profile',
    'search_posts': 'search', 'search_results_new_page': 'search',
    'course_comparer': 'match', 'volunteer_hours': 'volunteer',
    'all_notifications': 'notifications', 'course_page': 'course',
    'timetable_assigner': 'atlas', 'followed_posts': 'bookmarks', 'my_posts': 'my_posts',
    'site_info': 'about', 'privacy_policy': 'privacy',
}
METRICS = {
    'unique_users': 'Unique signed-in users',
    'page_screen_opens': 'Page / screen opens',
    'post_opens': 'Post opens',
    'post_interactions': 'Post interactions',
    'match_users': 'People using Match',
    'profile_search_users': 'People searching profiles',
    'volunteer_hours_users': 'People opening volunteer hours',
    'web_opens': 'Web page opens',
    'mobile_opens': 'Native mobile screen opens',
    'web_unique_users': 'Unique web users',
    'mobile_unique_users': 'Unique native mobile users',
}


class AnalyticsPlatformMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        platform = request.headers.get('X-WolfKey-Platform')
        if platform not in ('web', 'mobile'):
            platform = 'mobile' if request.headers.get('Authorization', '').startswith('Token ') else 'web'
        token = request_platform.set(platform)
        try:
            return self.get_response(request)
        finally:
            request_platform.reset(token)


def record_event(user, event_type, screen, *, platform=None, event_id=None):
    """Use a savepoint so telemetry errors cannot poison a business transaction."""
    if not user or not user.is_authenticated:
        return False
    try:
        with transaction.atomic():
            values = dict(account_id=user.pk, platform=platform or request_platform.get(),
                          event_type=event_type, screen=screen)
            if event_id is None:
                AnalyticsEvent.objects.create(**values)
            else:
                AnalyticsEvent.objects.get_or_create(id=event_id, defaults=values)
        return True
    except Exception:
        logger.exception('Analytics event could not be recorded')
        return False


def record_interaction(user):
    # An outer business transaction must commit before its event is recorded.
    platform = request_platform.get()
    transaction.on_commit(lambda: record_event(user, 'post_interaction', 'post_detail', platform=platform))


def daily_rows(start, end, selected, coverage):
    first = datetime.combine(start, time.min, VANCOUVER)
    last = datetime.combine(end + timedelta(days=1), time.min, VANCOUVER)
    opens = Q(event_type='screen_open')
    expressions = {
        'unique_users': Count('account_id', distinct=True),
        'page_screen_opens': Count('id', filter=opens),
        'post_opens': Count('id', filter=opens & Q(screen='post_detail')),
        'post_interactions': Count('id', filter=Q(event_type='post_interaction')),
        'match_users': Count('account_id', distinct=True, filter=Q(event_type='match_open')),
        'profile_search_users': Count('account_id', distinct=True, filter=Q(event_type='profile_search')),
        'volunteer_hours_users': Count('account_id', distinct=True, filter=Q(event_type='volunteer_open')),
        'web_opens': Count('id', filter=opens & Q(platform='web')),
        'mobile_opens': Count('id', filter=opens & Q(platform='mobile')),
        'web_unique_users': Count('account_id', distinct=True, filter=Q(platform='web')),
        'mobile_unique_users': Count('account_id', distinct=True, filter=Q(platform='mobile')),
    }
    counts = AnalyticsEvent.objects.filter(occurred_at__gte=first, occurred_at__lt=last)
    counts = counts.annotate(day=TruncDate('occurred_at', tzinfo=VANCOUVER)).values('day')
    counts = counts.annotate(**{key: expressions[key] for key in selected}).order_by('day')
    by_date = {row['day']: row for row in counts}
    tracking_date = timezone.localtime(coverage, VANCOUVER).date() if coverage else None
    day = start
    while day <= end:
        available = tracking_date is not None and day >= tracking_date
        values = by_date.get(day, {})
        yield [day.isoformat()] + [values.get(key, 0) if available else '' for key in selected]
        day += timedelta(days=1)
