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
    """
    Token-authenticated API: return a processed schedule for a user for a given date.
    
    Query Parameters:
        date (str, optional): Date in YYYY-MM-DD format. Defaults to today in PST.
    
    Returns:
        Response: JSON response with:
            - schedule (List[Dict]): Processed schedule with course names and times
            - early_dismissal (bool): Whether it's an early dismissal day
            - late_start (bool): Whether it's a late start day
    """
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

        return Response({
            'schedule': processed,
            'early_dismissal': raw_schedule.get('early_dismissal', False),
            'late_start': raw_schedule.get('late_start', False)
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response({'error': 'Invalid date format', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Error in process_schedule_api: {e}")
        return Response({'error': 'User or profile not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_daily_schedule(request, target_date):
    """
    Token-authenticated API: return block order and times for a given ISO date.
    
    Args:
        target_date (str): Date in YYYY-MM-DD format
    
    Returns:
        Response: JSON response with:
            - date (str): Formatted date string
            - blocks (List[Optional[str]]): List of block identifiers
            - times (List[Optional[str]]): List of time ranges
            - early_dismissal (bool): Whether it's an early dismissal day
            - late_start (bool): Whether it's a late start day
    """
    try:
        schedule = get_block_order_for_day(target_date)
        date_obj = _parse_iso_date(target_date)
        formatted_date = _convert_to_sheet_date_format(date_obj)

        return Response({
            'date': formatted_date,
            'blocks': schedule['blocks'],
            'times': schedule['times'],
            'early_dismissal': schedule.get('early_dismissal', False),
            'late_start': schedule.get('late_start', False)
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
    """
    Token-authenticated API: return a user's course blocks.
    
    Args:
        user_id (int): ID of the user to fetch blocks for
    
    Returns:
        Response: JSON response with user's course block information
    """
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
    """
    Check if ceremonial uniform is required for a specific date.
    
    Args:
        target_date (str): Date in YYYY-MM-DD format
    
    Returns:
        Response: JSON response with:
            - date (str): Formatted date string
            - ceremonial_uniform_required (bool): Whether ceremonial uniform is required
    """
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