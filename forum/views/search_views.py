from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.contrib.postgres.search import TrigramSimilarity
from forum.models import Post, User
from forum.views.utils import process_post_preview, add_course_context
from forum.views.greetings import get_random_greeting
from forum.views.course_views import get_user_courses
from django.db.models import F
from forum.views.schedule_views import get_block_order_for_day, process_schedule_for_user, is_ceremonial_uniform_required
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Count
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import HttpResponse


@login_required
def for_you(request):
    if not request.user.is_authenticated:
        return redirect('login')

    experienced_courses, help_needed_courses = get_user_courses(request.user)

    greeting = get_random_greeting(request.user.first_name, user_timezone="America/Vancouver")

    # Get today's and tomorrow's dates in the required format
    pst = ZoneInfo("America/Los_Angeles")
    now_pst = datetime.now(pst)
    today = now_pst.strftime("%a, %b %d").lstrip("0").replace(" 0", " ")
    tomorrow = (now_pst + timedelta(days=1)).strftime("%a, %b %d").lstrip("0").replace(" 0", " ")

    ceremonial_required_today = is_ceremonial_uniform_required(request.user, today)
    ceremonial_required_tomorrow = is_ceremonial_uniform_required(request.user, tomorrow)

    # Fetch raw schedules
    raw_schedule_today = get_block_order_for_day(today)
    raw_schedule_tomorrow = get_block_order_for_day(tomorrow)

    # Process the schedules for the user
    processed_schedule_today = process_schedule_for_user(request.user, raw_schedule_today)
    processed_schedule_tomorrow = process_schedule_for_user(request.user, raw_schedule_tomorrow)


    # Get posts that the user needs help or is expierenced in, taking currently, or posts posted by user
    user_profile = request.user.userprofile

    current_courses = list(filter(None, [
        user_profile.block_1A,
        user_profile.block_1B,
        user_profile.block_1D,
        user_profile.block_1E,
        user_profile.block_2A,
        user_profile.block_2B,
        user_profile.block_2C,
        user_profile.block_2D,
        user_profile.block_2E
    ]))

    posts = Post.objects.filter(
        Q(courses__in=experienced_courses) | 
        Q(courses__in=help_needed_courses) | 
        Q(author=request.user) |
        Q(courses__in=current_courses)
    ).annotate(
        solution_count=Count('solutions', distinct=True),
        comment_count=Count('solutions__comments', distinct=True),
        total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True)
    ).distinct().order_by('-created_at')

    # Process posts
    for post in posts:
        post.preview_text = process_post_preview(post)
        add_course_context(post, experienced_courses, help_needed_courses)

    # Pagination
    paginator = Paginator(posts, 10)
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        return HttpResponse('')  # Return empty response when no more posts
    

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'forum/components/post_list.html', {'posts': posts})

    return render(request, 'forum/for_you.html', {
        'posts': posts,
        'greeting': greeting,
        'current_date': today,
        'tomorrow_date': tomorrow,
        'schedule_today': processed_schedule_today,
        'schedule_tomorrow': processed_schedule_tomorrow,
        'ceremonial_required_today': ceremonial_required_today, 
        'ceremonial_required_tomorrow': ceremonial_required_tomorrow,
    })

def all_posts(request):
    query = request.GET.get('q', '')

    posts = Post.objects.annotate(
        solution_count=Count('solutions', distinct=True),
        comment_count=Count('solutions__comments', distinct=True),
        total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True)
    ).order_by('-created_at')


    if query:
        search_query = SearchQuery(query)
        posts = posts.annotate(
            rank=SearchRank(F('search_vector'), search_query) + TrigramSimilarity('title', query)
        ).filter(rank__gte=0.3).order_by('-rank')


    experienced_courses, help_needed_courses = get_user_courses(request.user)
    
    # Process posts
    for post in posts:
        post.preview_text = process_post_preview(post)
        add_course_context(post, experienced_courses, help_needed_courses)

    paginator = Paginator(posts, 10)
    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        return HttpResponse('')  # Return empty response when no more posts

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'forum/components/post_list.html', {'posts': posts})

    return render(request, 'forum/all_posts.html', {
        'posts': posts,
        'query': query,
    })



def search_results_new_page(request):
    query = request.GET.get('q', '')
    posts = Post.objects.all().order_by('-created_at')
    users = User.objects.all()

    if query:
        search_query = SearchQuery(query)

        # Search in posts
        posts = posts.annotate(
            rank=SearchRank(F('search_vector'), search_query) + TrigramSimilarity('title', query),
            
            solution_count=Count('solutions', distinct=True),
            comment_count=Count('solutions__comments', distinct=True),
            total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True)
        ).filter(rank__gte=0.3).order_by('-rank')

        # Search in users
        users = users.annotate(
            rank=SearchRank(F('search_vector'), search_query),
        ).filter(rank__gte=0.3).order_by('-rank')

        experienced_courses, help_needed_courses = get_user_courses(request.user)

        # Process posts
        for post in posts:
            post.preview_text = process_post_preview(post)
            add_course_context(post, experienced_courses, help_needed_courses)

        return render(request, 'forum/search_results.html', {
            'posts': posts,
            'users': users,
            'query': query
        })

    return redirect('all_posts')


@login_required
def my_posts(request):
    posts = Post.objects.filter(author = request.user)
    experienced_courses, help_needed_courses = get_user_courses(request.user)
    
    # Process posts
    for post in posts:
        post.preview_text = process_post_preview(post)
        add_course_context(post, experienced_courses, help_needed_courses)
    return render(request,'forum/my_posts.html', {'posts': posts})