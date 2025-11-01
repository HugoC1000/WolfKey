from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from forum.services.schedule_services import (
    get_block_order_for_day,
    _parse_iso_date,
    _convert_to_sheet_date_format,
    process_schedule_for_user,
)


@require_http_methods(["GET"])
def daily_schedule_view(request, target_date):
    """Session/CSRF-protected view for the website to fetch the daily schedule."""
    try:
        schedule = get_block_order_for_day(target_date)
        date_obj = _parse_iso_date(target_date)
        formatted_date = _convert_to_sheet_date_format(date_obj)

        return JsonResponse({
            'date': formatted_date,
            'blocks': schedule['blocks'],
            'times': schedule['times']
        })
    except ValueError as e:
        return JsonResponse({'error': 'Invalid date format. Expected YYYY-MM-DD', 'details': str(e)}, status=400)
    except Exception as e:
        print(f"Error in daily_schedule_view: {e}")
        return JsonResponse({'error': 'Internal server error', 'details': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def user_blocks_view(request, user_id):
    """Session/CSRF-protected view to the user's blocks."""
    from django.shortcuts import get_object_or_404
    from forum.models import User, UserProfile
    from forum.serializers import BlockSerializer

    try:
        user = get_object_or_404(User, id=user_id)
        user_profile = get_object_or_404(UserProfile, user=user)
        
        # Check if user allows schedule comparison
        if not user_profile.allow_schedule_comparison:
            return JsonResponse({
                'error': 'This user has disabled schedule comparison'
            }, status=403)

        serializer = BlockSerializer(user_profile)
        return JsonResponse(serializer.data)

    except Exception as e:
        print(f"Error in user_schedule_view: {e}")
        return JsonResponse({'error': 'User or profile not found'}, status=404)
