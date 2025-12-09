from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from forum.services.feed_services import get_for_you_posts, get_all_posts, paginate_posts, get_user_posts
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

    posts, page_obj = get_all_posts(request.user, query, page)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'forum/components/post_list.html', {'posts': posts, 'page_obj': page_obj})

    # Get schedule info
    pst = ZoneInfo("America/Los_Angeles")
    now_pst = datetime.now(pst)
    tomorrow_pst = now_pst + timedelta(days=1)
    
    # If tomorrow is Saturday (5) or Sunday (6), show Monday's schedule instead
    if tomorrow_pst.weekday() in [5, 6]:  # 5 = Saturday, 6 = Sunday
        # Calculate days until Monday
        days_until_monday = (7 - tomorrow_pst.weekday()) % 7
        if days_until_monday == 0:  # If tomorrow is already Sunday
            days_until_monday = 1
        tomorrow_pst = tomorrow_pst + timedelta(days=days_until_monday)

    today_iso = _get_iso_date(now_pst)
    tomorrow_iso = _get_iso_date(tomorrow_pst)

    greeting = get_random_greeting(request.user.first_name, user_timezone="America/Vancouver")

    try:
        ceremonial_required_today = is_ceremonial_uniform_required(request.user, today_iso)
        ceremonial_required_tomorrow = is_ceremonial_uniform_required(request.user, tomorrow_iso)
        
        raw_schedule_today = get_block_order_for_day(today_iso)
        raw_schedule_tomorrow = get_block_order_for_day(tomorrow_iso)
        processed_schedule_today = process_schedule_for_user(request.user, raw_schedule_today)
        processed_schedule_tomorrow = process_schedule_for_user(request.user, raw_schedule_tomorrow)
        
        # Extract flags from raw schedules
        early_dismissal_today = raw_schedule_today.get('early_dismissal', False)
        late_start_today = raw_schedule_today.get('late_start', False)
        early_dismissal_tomorrow = raw_schedule_tomorrow.get('early_dismissal', False)
        late_start_tomorrow = raw_schedule_tomorrow.get('late_start', False)
    except Exception as e:
        print(e)
        ceremonial_required_today = None
        ceremonial_required_tomorrow = None
        processed_schedule_today = None
        processed_schedule_tomorrow = None
        early_dismissal_today = False
        late_start_today = False
        early_dismissal_tomorrow = False
        late_start_tomorrow = False

    # Convert dates to display format
    today_display = _convert_to_sheet_date_format(now_pst.date())
    tomorrow_display = _convert_to_sheet_date_format(tomorrow_pst.date())
    
    # Determine the schedule title based on day of week
    if tomorrow_pst.weekday() == 0:  # Monday
        # Check if we jumped from weekend to Monday
        actual_tomorrow = now_pst + timedelta(days=1)
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
        'tomorrow_iso': tomorrow_iso,
        'schedule_title': schedule_title,
        'schedule_today': processed_schedule_today,
        'schedule_tomorrow': processed_schedule_tomorrow,
        'ceremonial_required_today': ceremonial_required_today,
        'ceremonial_required_tomorrow': ceremonial_required_tomorrow,
        'early_dismissal_today': early_dismissal_today,
        'late_start_today': late_start_today,
        'early_dismissal_tomorrow': early_dismissal_tomorrow,
        'late_start_tomorrow': late_start_tomorrow,
    })

def all_posts(request):
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    posts, page_obj = get_all_posts(request.user, query, page)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'forum/components/post_list.html', {'posts': posts})

    return render(request, 'forum/all_posts.html', {
        'posts': posts,
        'query': query,
    })

@login_required
def my_posts(request):
    posts = get_user_posts(request.user)
    return render(request, 'forum/my_posts.html', {'posts': posts})