from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.contrib.postgres.search import TrigramSimilarity
from forum.models import Post
from forum.views.utils import process_post_preview, add_course_context
from forum.views.greetings import get_random_greeting
from forum.views.course_views import get_user_courses
from django.db.models import F
from forum.views.schedule_views import get_block_order_for_day, process_schedule_for_user, is_ceremonial_uniform_required
import datetime

@login_required
def for_you(request):
    if not request.user.is_authenticated:
        return redirect('login')

    experienced_courses, help_needed_courses = get_user_courses(request.user)

    greeting = get_random_greeting(request.user.first_name, user_timezone="America/Vancouver")

    # Get today's and tomorrow's dates in the required format
    today = datetime.datetime.now().strftime("%a, %b %d")
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%a, %b %d")

    ceremonial_required_today = is_ceremonial_uniform_required(request.user, today)
    ceremonial_required_tomorrow = is_ceremonial_uniform_required(request.user, tomorrow)

    # Fetch raw schedules
    raw_schedule_today = get_block_order_for_day(today)
    raw_schedule_tomorrow = get_block_order_for_day(tomorrow)

    # Process the schedules for the user
    processed_schedule_today = process_schedule_for_user(request.user, raw_schedule_today)
    processed_schedule_tomorrow = process_schedule_for_user(request.user, raw_schedule_tomorrow)

    # Get posts for both types of courses
    posts = Post.objects.filter(
        Q(courses__in=experienced_courses) | 
        Q(courses__in=help_needed_courses)
    ).distinct().order_by('-created_at')

    # Process posts
    for post in posts:
        post.preview_text = process_post_preview(post)
        add_course_context(post, experienced_courses, help_needed_courses)

    return render(request, 'forum/for_you.html', {
        'posts': posts,
        'experienced_courses': experienced_courses,
        'help_needed_courses': help_needed_courses,
        'greeting': greeting,
        'schedule_today': processed_schedule_today,
        'schedule_tomorrow': processed_schedule_tomorrow,
        'ceremonial_required_today': ceremonial_required_today, 
        'ceremonial_required_tomorrow': ceremonial_required_tomorrow
    })

def all_posts(request):
    query = request.GET.get('q', '')
    posts = Post.objects.all().order_by('-created_at')

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

    return render(request, 'forum/all_posts.html', {
        'posts': posts,
        'query': query,
    })



def search_results_new_page(request):
    # print("Enters view")
    query = request.GET.get('q', '')
    posts = Post.objects.all().order_by('-created_at')

    if query:
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

        return render(request, 'forum/search_results.html', {
                'posts': posts,
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