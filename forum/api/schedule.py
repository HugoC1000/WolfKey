from datetime import datetime, date
from zoneinfo import ZoneInfo
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from forum.services.schedule_services import (
    get_block_order_for_day,
    _parse_iso_date,
    _convert_to_sheet_date_format,
    is_ceremonial_uniform_required,
    process_schedule_for_user,
)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def process_schedule_api(request, user_id):
    """Token-authenticated API: return a processed schedule for a user for a given date (query param `date` or today)."""
    from django.shortcuts import get_object_or_404
    from forum.models import User

    try:
        user = get_object_or_404(User, id=user_id)

        # allow optional date param (ISO format), default to today's date in PST
        pst = ZoneInfo("America/Los_Angeles")
        now_pst = datetime.now(pst)
        target_date = request.query_params.get('date') or now_pst.date().isoformat()
        raw_schedule = get_block_order_for_day(target_date)
        processed = process_schedule_for_user(user, raw_schedule)

        return Response({'schedule': processed}, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({'error': 'Invalid date format', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in process_schedule_api: {e}")
        return Response({'error': 'User or profile not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_daily_schedule(request, target_date):
    """Token-authenticated API: return block order and times for a given ISO date."""
    try:
        schedule = get_block_order_for_day(target_date)
        date_obj = _parse_iso_date(target_date)
        formatted_date = _convert_to_sheet_date_format(date_obj)

        return Response({
            'date': formatted_date,
            'blocks': schedule['blocks'],
            'times': schedule['times']
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({
            'error': 'Invalid date format. Expected YYYY-MM-DD',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in get_daily_schedule: {e}")
        return Response({
            'error': 'Internal server error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_user_blocks_api(request, user_id):
    """Token-authenticated API: return a processed schedule for a user (for today's date)."""
    from django.shortcuts import get_object_or_404
    from forum.models import User, UserProfile
    from forum.serializers import BlockSerializer

    try:
        user = get_object_or_404(User, id=user_id)
        user_profile = get_object_or_404(UserProfile, user=user)
        
        # Check if user allows schedule comparison
        if not user_profile.allow_schedule_comparison:
            return Response({
                'error': 'This user has disabled schedule comparison'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = BlockSerializer(user_profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Error in get_user_schedule_api: {e}")
        return Response({'error': 'User or profile not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def check_ceremonial_uniform(request, target_date):
    """Check if ceremonial uniform is required for a specific date"""

    try:
        is_required = is_ceremonial_uniform_required(user=request.user, iso_date=target_date)
        date_obj = _parse_iso_date(target_date)
        formatted_date = _convert_to_sheet_date_format(date_obj)
        
        return Response({
            'date': formatted_date,
            'ceremonial_uniform_required': is_required
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({
            'error': 'Invalid date format. Expected YYYY-MM-DD',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in check_ceremonial_uniform: {e}")
        return Response({
            'error': 'Internal server error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)