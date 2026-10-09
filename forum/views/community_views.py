from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from forum.services.community_services import (
    add_community_lunch_service,
    delete_community_lunch_service,
    get_community_directory,
    toggle_community_follow_service,
    toggle_community_subscription_service,
    update_community_lunch_service,
)
from forum.services.feed_services import get_community_posts
from forum.views.json_responses import error_payload, success_payload


def _lunch_data(lunch):
    return {
        'id': lunch.id,
        'date': lunch.date.isoformat(),
        'location': lunch.location,
        'update_url': reverse('update_community_lunch', args=[lunch.id]),
        'delete_url': reverse('delete_community_lunch', args=[lunch.id]),
    }


def community(request):
    page_obj = get_community_posts(request.user, request.GET.get('page', 1))
    posts = list(page_obj.object_list)
    accounts, followed_ids, subscription_ids = get_community_directory(request.user)
    return render(request, 'forum/community.html', {
        'posts': posts,
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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if 'error' in result:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        message = (
            f"You joined {result['community'].get_full_name()} and its mailing list."
            if result['following'] else f"You left {result['community'].get_full_name()}."
        )
        return JsonResponse(success_payload({
            'following': result['following'],
            'mailing_list_joined': result['mailing_list_joined'],
        }, message))
    if 'error' in result:
        if result['status'] == 404:
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
        if result['status'] == 404:
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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if 'error' in result:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        message = 'Lunch date added.' if result['created'] else 'That lunch date is already listed.'
        return JsonResponse(success_payload(_lunch_data(result['lunch']), message), status=201 if result['created'] else 200)
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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if 'error' in result:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        return JsonResponse(success_payload(_lunch_data(result['lunch']), 'Lunch updated.'))
    if 'error' in result:
        messages.error(request, result['error'])
    else:
        messages.success(request, 'Lunch updated.')
    return _community_action_redirect(request)


@login_required
@require_POST
def delete_community_lunch(request, lunch_id):
    result = delete_community_lunch_service(request.user, lunch_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if 'error' in result:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        return JsonResponse(success_payload(None, 'Lunch date removed.'))
    if 'error' in result:
        messages.error(request, result['error'])
    else:
        messages.success(request, 'Lunch date removed.')
    return _community_action_redirect(request)
