from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from forum.services.feed_services import get_for_you_posts, get_all_posts, paginate_posts, get_user_posts
from forum.serializers import PostListSerializer, attach_poll_data_to_posts
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

    page_obj = get_all_posts(request.user, query, page)
    posts = list(page_obj.object_list)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'forum/components/post_list.html', {
            'posts': posts,
            'posts_data': posts_data,
            'page_obj': page_obj
        })

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
        'posts_data': posts_data,
        'greeting': greeting,
        'current_date': today_display,
        'tomorrow_date': tomorrow_display,
        'today_iso': today_iso,
        'tomorrow_iso': tomorrow_iso,
        'schedule_title': schedule_title,
    })

def all_posts(request):
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    page_obj = get_all_posts(request.user, query, page)
    posts = list(page_obj.object_list)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'forum/components/post_list.html', {
            'posts': posts,
            'posts_data': posts_data,
            'page_obj': page_obj
        })

    return render(request, 'forum/all_posts.html', {
        'posts': posts,
        'posts_data': posts_data,
        'query': query,
        'page_obj': page_obj
    })

@login_required
def my_posts(request):
    page_obj = get_user_posts(request.user)
    posts = list(page_obj.object_list)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)
    return render(request, 'forum/my_posts.html', {
        'posts': posts,
        'posts_data': posts_data,
        'page_obj': page_obj
    })