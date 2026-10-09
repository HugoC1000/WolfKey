from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from forum.services.volunteer_service import (
    delete_milestone as delete_milestone_service,
    delete_resource as delete_resource_service,
    get_volunteer_admin_data,
    is_volunteer_admin,
    save_milestone,
    save_resource,
)


def _volunteer_action_response(request, result):
    if 'error' in result:
        if result['status'] == 404:
            raise Http404(result['error'])
        messages.error(request, result['error'])
    else:
        messages.success(request, result['message'])
    return redirect('volunteer_admin')


@login_required
@user_passes_test(is_volunteer_admin)
def volunteer_admin_page(request):
    return render(request, 'forum/volunteer_admin.html', get_volunteer_admin_data())


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def create_milestone(request):
    return _volunteer_action_response(request, save_milestone(request.user, request.POST))


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def update_milestone(request, milestone_id):
    return _volunteer_action_response(request, save_milestone(request.user, request.POST, milestone_id))


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def delete_milestone(request, milestone_id):
    return _volunteer_action_response(request, delete_milestone_service(request.user, milestone_id))


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def create_resource(request):
    return _volunteer_action_response(request, save_resource(request.user, request.POST))


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def update_resource(request, resource_id):
    return _volunteer_action_response(request, save_resource(request.user, request.POST, resource_id))


@login_required
@user_passes_test(is_volunteer_admin)
@require_POST
def delete_resource(request, resource_id):
    return _volunteer_action_response(request, delete_resource_service(request.user, resource_id))
