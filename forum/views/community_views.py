from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from forum.serializers import PostListSerializer
from forum.services.community_services import (
    add_community_lunch_service,
    delete_community_lunch_service,
    get_community_directory,
    toggle_community_follow_service,
    toggle_community_subscription_service,
    update_community_lunch_service,
)
from forum.services.feed_services import get_community_posts
from forum.services.poll_display_service import attach_poll_data_to_posts


def community(request):
    page_obj = get_community_posts(request.user, request.GET.get('page', 1))
    posts = list(page_obj.object_list)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)
    accounts, followed_ids, subscription_ids = get_community_directory(request.user)
    return render(request, 'forum/community.html', {
        'posts': posts,
        'posts_data': posts_data,
        'page_obj': page_obj,
        'community_accounts': accounts,
        'followed_community_ids': followed_ids,
        'subscription_community_ids': subscription_ids,
        'show_community_pins': True,
    })


def _community_action_redirect(request):
    next_url = request.POST.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('community')


@login_required
@require_POST
def toggle_community_follow(request, community_id):
    result = toggle_community_follow_service(request.user, community_id)
    if 'error' in result:
        if result.get('error_code') == 'community_unavailable':
            raise Http404(result['error'])
        messages.error(request, result['error'])
    elif result['following']:
        messages.success(
            request,
            f"You joined {result['community'].get_full_name()} and its mailing list.",
        )
    else:
        messages.success(request, f"You left {result['community'].get_full_name()}.")
    return _community_action_redirect(request)


@login_required
@require_POST
def toggle_community_subscription(request, community_id):
    result = toggle_community_subscription_service(request.user, community_id)
    if 'error' in result:
        if result.get('error_code') == 'community_unavailable':
            raise Http404(result['error'])
        messages.error(request, result['error'])
    else:
        state = 'enabled' if result['subscribed'] else 'disabled'
        messages.success(
            request,
            f"Email updates from {result['community'].get_full_name()} are {state}.",
        )
    return _community_action_redirect(request)


@login_required
@require_POST
def add_community_lunch(request):
    result = add_community_lunch_service(
        request.user,
        request.POST.get('date'),
        request.POST.get('location'),
    )
    if 'error' in result:
        messages.error(request, result['error'])
    elif result['created']:
        messages.success(request, 'Lunch date added.')
    else:
        messages.info(request, 'That lunch date is already listed.')
    return _community_action_redirect(request)


@login_required
@require_POST
def update_community_lunch(request, lunch_id):
    update_values = {'location': request.POST.get('location')}
    if 'date' in request.POST:
        update_values['date_value'] = request.POST.get('date')
    result = update_community_lunch_service(request.user, lunch_id, **update_values)
    if 'error' in result:
        messages.error(request, result['error'])
    else:
        messages.success(request, 'Lunch updated.')
    return _community_action_redirect(request)


@login_required
@require_POST
def delete_community_lunch(request, lunch_id):
    result = delete_community_lunch_service(request.user, lunch_id)
    if 'error' in result:
        messages.error(request, result['error'])
    else:
        messages.success(request, 'Lunch date removed.')
    return _community_action_redirect(request)
