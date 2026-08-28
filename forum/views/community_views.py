from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render

from forum.serializers import PostListSerializer
from forum.services.community_services import (
    get_community_directory,
    toggle_community_follow_service,
    toggle_community_subscription_service,
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


@login_required
def toggle_community_follow(request, community_id):
    if request.method != 'POST':
        return HttpResponseForbidden('POST required')
    result = toggle_community_follow_service(request.user, community_id)
    if 'error' in result:
        if result.get('error_code') == 'community_unavailable':
            raise Http404(result['error'])
        messages.error(request, result['error'])
    elif result['following']:
        messages.success(
            request,
            f"You are following {result['community'].get_full_name()} and joined its mailing list.",
        )
    else:
        messages.success(request, f"You unfollowed {result['community'].get_full_name()}.")
    return redirect('community')


@login_required
def toggle_community_subscription(request, community_id):
    if request.method != 'POST':
        return HttpResponseForbidden('POST required')
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
    return redirect('community')
