from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse

# Import the new service layer
from forum.services.profile_service import (
    PROFILE_FIELDS,
    get_profile_user,
    get_profile_context,
    update_profile_info,
    update_privacy_preferences,
    update_profile_picture,
    update_profile_courses,
    add_user_experience,
    add_user_help_request,
    remove_user_experience,
    remove_user_help_request,
)
from forum.serializers import UserProfileSerializer
from forum.services.results import service_error
from forum.views.json_responses import error_payload, success_payload

def _profile_fields(data):
    return {field: data.get(field) for field in PROFILE_FIELDS if field in data}


@login_required
def profile_view(request, username):
    if request.method == 'POST':
        profile_user = get_profile_user(username)
        if profile_user is None:
            from django.http import Http404
            raise Http404('User not found')
        form_type = request.POST.get('form_type')
        if request.user != profile_user:
            result = service_error('You can only update your own profile.', 403)
        elif form_type == 'privacy_preferences':
            result = update_privacy_preferences(
                profile_user,
                allow_schedule_comparison='allow_schedule_comparison' in request.POST,
                display_email='display_email' in request.POST,
            )
        else:
            result = update_profile_info(
                request.user, profile_user, _profile_fields(request.POST)
            )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if 'error' not in result:
                return JsonResponse(success_payload(None, result['message']))
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        if 'error' not in result:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['error'])
        return redirect('profile', username=request.user.username)
    
    profile_user = get_profile_user(username)
    if profile_user is None:
        from django.http import Http404
        raise Http404('User not found')
    profile_data = UserProfileSerializer(
        profile_user.userprofile, context={'request': request}
    ).data
    context = get_profile_context(request.user, profile_user, profile_data)
    
    return render(request, 'forum/profile.html', context)

@login_required
def upload_profile_picture(request):
    is_fetch = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST' and request.FILES.get('profile_picture'):
        result = update_profile_picture(request.user, request.FILES.get('profile_picture'))
        if is_fetch:
            if 'error' not in result:
                picture_url = UserProfileSerializer(
                    request.user.userprofile, context={'request': request}
                ).data['profile_picture']
                return JsonResponse(success_payload(
                    {'profile_picture_url': picture_url}, result['message']
                ))
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        if 'error' not in result:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['error'])
        return redirect('my_profile')
    if is_fetch:
        return JsonResponse(error_payload('A profile picture is required.'), status=400)
    return render(request, 'forum/upload_profile_picture.html')

@login_required
def my_profile(request):
    return redirect('profile', username=request.user.username)

@login_required
def add_experience(request):
    if request.method == 'POST':
        result = add_user_experience(request.user, request.POST.get('course'))
        if 'error' not in result:
            return JsonResponse(success_payload({
                'id': result['id'],
                'course_id': result['course_id'],
                'course_name': result['course_name'],
                'remove_url': reverse('remove_experience', args=[result['id']]),
            }, result['message']))
        else:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    return JsonResponse(error_payload('Invalid request method.'), status=405)

@login_required
def add_help_request(request):
    if request.method == 'POST':
        result = add_user_help_request(request.user, request.POST.get('course'))
        if 'error' not in result:
            return JsonResponse(success_payload({
                'id': result['id'],
                'course_id': result['course_id'],
                'course_name': result['course_name'],
                'remove_url': reverse('remove_help_request', args=[result['id']]),
            }, result['message']))
        else:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    return JsonResponse(error_payload('Invalid request method.'), status=405)

@login_required
def remove_experience(request, experience_id):
    if request.method == 'POST':
        result = remove_user_experience(request.user, experience_id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if 'error' not in result:
                return JsonResponse(success_payload(
                    {'course_id': result['course_id']}, result['message']
                ))
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        if 'error' not in result:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['error'])
    return redirect('profile', username=request.user.username)

@login_required
def remove_help_request(request, help_id):
    if request.method == 'POST':
        result = remove_user_help_request(request.user, help_id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if 'error' not in result:
                return JsonResponse(success_payload(
                    {'course_id': result['course_id']}, result['message']
                ))
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        if 'error' not in result:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['error'])
    return redirect('profile', username=request.user.username)

@login_required
def update_courses(request):
    if request.method == 'POST':
        result = update_profile_courses(request.user, request.POST)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if 'error' not in result:
                return JsonResponse(success_payload(None, result['message']))
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        if 'error' not in result:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['error'])
        return redirect('profile', username=request.user.username)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(error_payload('Invalid request method.'), status=405)
    return redirect('profile', username=request.user.username)
