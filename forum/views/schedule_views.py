from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from forum.services.schedule_services import (
    get_block_order_for_day,
    _parse_iso_date,
    _convert_to_sheet_date_format,
    process_schedule_for_user,
    is_ceremonial_uniform_required,
    get_user_blocks_for_viewer,
)
from forum.serializers import serialize_community_lunches_for_schedule
from forum.views.json_responses import error_payload, success_payload


@require_http_methods(["GET"])
def daily_schedule_view(request, target_date):
    """
    Session/CSRF-protected view for the website to fetch the daily schedule.
    
    Args:
        target_date (str): Date in YYYY-MM-DD format
    
    Returns:
        JsonResponse: JSON response with:
            - date (str): Formatted date string
            - blocks (List[Optional[str]]): List of block identifiers (or processed schedule if user is authenticated)
            - times (List[Optional[str]]): List of time ranges
            - early_dismissal (bool): Whether it's an early dismissal day
            - late_start (bool): Whether it's a late start day
            - ceremonial_required (bool): Whether ceremonial uniform is required (if user is authenticated)
    """
    try:
        calendar_context = {}
        schedule = get_block_order_for_day(target_date, calendar_context)
        
        if schedule is None:
            return JsonResponse(error_payload('Failed to get schedule', 500), status=500)
        
        date_obj = _parse_iso_date(target_date)
        formatted_date = _convert_to_sheet_date_format(date_obj)

        response_data = {
            'date': formatted_date,
            'early_dismissal': schedule.get('early_dismissal', False),
            'late_start': schedule.get('late_start', False),
            'community_lunches': serialize_community_lunches_for_schedule(date_obj, schedule['blocks']),
        }
        
        # If user is authenticated, process schedule for them and include ceremonial uniform
        if request.user.is_authenticated:
            processed_schedule = process_schedule_for_user(request.user, schedule)
            ceremonial_required = is_ceremonial_uniform_required(target_date, calendar_context)
            response_data['schedule'] = processed_schedule
            response_data['ceremonial_required'] = ceremonial_required
        else:
            # Return raw blocks and times for unauthenticated users
            response_data['blocks'] = schedule['blocks']
            response_data['times'] = schedule['times']
        
        return JsonResponse(success_payload(response_data))
    except ValueError as e:
        return JsonResponse(error_payload('Invalid date format. Expected YYYY-MM-DD'), status=400)
    except Exception as e:
        print(f"Error in daily_schedule_view: {e}")
        return JsonResponse(error_payload('Internal server error', 500), status=500)


@login_required
@require_http_methods(["GET"])
def user_blocks_view(request, user_id):
    """
    Session/CSRF-protected view to get a user's course blocks.
    
    Args:
        user_id (int): ID of the user to fetch blocks for
    
    Returns:
        JsonResponse: JSON response with user's course block information
    """
    from forum.serializers import UserScheduleSerializer

    try:
        result = get_user_blocks_for_viewer(request.user, user_id)
        if 'error' in result:
            return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
        serializer = UserScheduleSerializer(result['profile'])
        return JsonResponse(success_payload(serializer.data))

    except Exception as e:
        print(f"Error in user_schedule_view: {e}")
        return JsonResponse(error_payload('User or profile not found', 404), status=404)
