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
    except Exception as e:
        print(e)
        ceremonial_required_today = None
        ceremonial_required_tomorrow = None

        processed_schedule_today = None
        processed_schedule_tomorrow = None

    # Convert dates to display format
    today_display = _convert_to_sheet_date_format(now_pst.date())
    tomorrow_display = _convert_to_sheet_date_format(tomorrow_pst.date())

    return render(request, 'forum/for_you.html', {
        'posts': posts,
        'greeting': greeting,
        'current_date': today_display,
        'tomorrow_date': tomorrow_display,
        'schedule_today': processed_schedule_today,
        'schedule_tomorrow': processed_schedule_tomorrow,
        'ceremonial_required_today': ceremonial_required_today,
        'ceremonial_required_tomorrow': ceremonial_required_tomorrow,
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