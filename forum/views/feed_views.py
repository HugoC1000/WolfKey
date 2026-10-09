from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from forum.services.feed_services import get_for_you_posts, get_all_posts, get_user_posts
from forum.services.schedule_services import (
    get_block_order_for_day,
    process_schedule_for_user,
    is_ceremonial_uniform_required,
    _convert_to_sheet_date_format
)
from forum.views.greetings import get_random_greeting
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def _get_iso_date(dt):
    """Convert datetime to ISO format date string (YYYY-MM-DD)"""
    return dt.strftime('%Y-%m-%d')

@login_required
def for_you(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    page = request.GET.get('page', 1)
    query = request.GET.get('q', '')

    # Keep the web home feed aligned with the mobile Home screen, which uses
    # the global all-posts feed rather than personalized course filtering.
    page_obj = get_all_posts(request.user, query, page)
    posts = list(page_obj.object_list)
    profile = getattr(request.user, 'userprofile', None)
    has_schedule_block = profile is not None and any(
        getattr(profile, f'{block}_id')
        for block in ('block_1A', 'block_1B', 'block_1D', 'block_1E',
                      'block_2A', 'block_2B', 'block_2C', 'block_2D', 'block_2E')
    )
    # Get schedule info
    school_timezone = ZoneInfo("America/Vancouver")
    now_school = datetime.now(school_timezone)
    tomorrow_school = now_school + timedelta(days=1)
    
    # If tomorrow is Saturday (5) or Sunday (6), show Monday's schedule instead
    if tomorrow_school.weekday() in [5, 6]:  # 5 = Saturday, 6 = Sunday
        # Calculate days until Monday
        days_until_monday = (7 - tomorrow_school.weekday()) % 7
        if days_until_monday == 0:  # If tomorrow is already Sunday
            days_until_monday = 1
        tomorrow_school = tomorrow_school + timedelta(days=days_until_monday)

    today_iso = _get_iso_date(now_school)
    tomorrow_iso = _get_iso_date(tomorrow_school)

    greeting = get_random_greeting(request.user.first_name, user_timezone="America/Vancouver")

    # Convert dates to display format
    today_display = _convert_to_sheet_date_format(now_school.date())
    tomorrow_display = _convert_to_sheet_date_format(tomorrow_school.date())
    
    # Determine the schedule title based on day of week
    if tomorrow_school.weekday() == 0:  # Monday
        # Check if we jumped from weekend to Monday
        actual_tomorrow = now_school + timedelta(days=1)
        if actual_tomorrow.weekday() in [5, 6]:  # If actual tomorrow is weekend
            schedule_title = "Monday's Schedule"
        else:
            schedule_title = "Tomorrow's Schedule"
    else:
        schedule_title = "Tomorrow's Schedule"

    return render(request, 'forum/for_you.html', {
        'posts': posts,
        'greeting': greeting,
        'current_date': today_display,
        'tomorrow_date': tomorrow_display,
        'today_iso': today_iso,
        'tomorrow_iso': tomorrow_iso,
        'schedule_title': schedule_title,
        'show_schedule_upload': not has_schedule_block,
    })

def all_posts(request):
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    page_obj = get_all_posts(request.user, query, page)
    posts = list(page_obj.object_list)
    return render(request, 'forum/all_posts.html', {
        'posts': posts,
        'query': query,
        'page_obj': page_obj
    })

def all_posts_fragment(request):
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    page_obj = get_all_posts(request.user, query, page)
    return render(request, 'forum/components/post_list.html', {
        'posts': list(page_obj.object_list),
        'page_obj': page_obj,
    })

@login_required
def my_posts(request):
    page_obj = get_user_posts(request.user)
    posts = list(page_obj.object_list)
    return render(request, 'forum/my_posts.html', {
        'posts': posts,
        'page_obj': page_obj
    })
