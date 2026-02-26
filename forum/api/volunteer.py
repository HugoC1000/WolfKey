"""
API endpoints for volunteer service hours
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from forum.models import VolunteerPinMilestone, VolunteerResource
from forum.serializers import VolunteerPinMilestoneSerializer, VolunteerResourceSerializer
from forum.services import volunteer_service
import gspread


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def volunteer_hours_api(request):
    """
    Get the current user's volunteer hours data including:
    - Total hours
    - Pin milestones with achievement status
    - Current pin
    - Next pin
    - Progress percentage to next pin
    - Available resources
    """
    user = request.user
    
    # Get user's volunteer hours using student_id
    try:
        user_hours = volunteer_service.get_volunteer_hours(user.student_id) if user.student_id else None
    except (gspread.SpreadsheetNotFound, Exception) as e:
        user_hours = None
    
    # If user hours not found, default to 0
    if user_hours is None:
        user_hours = 0.0
    
    # Get pin milestones from database
    db_milestones = VolunteerPinMilestone.objects.all().order_by('hours_required')
    
    # Serialize milestones with user hours context
    milestones_serializer = VolunteerPinMilestoneSerializer(
        db_milestones, 
        many=True, 
        context={'user_hours': user_hours}
    )
    
    # Calculate current pin and next pin
    current_pin = None
    next_pin = None
    progress_percentage = 0
    
    for milestone in milestones_serializer.data:
        if user_hours >= milestone['hours_required']:
            current_pin = milestone
        elif next_pin is None and user_hours < milestone['hours_required']:
            next_pin = milestone
    
    # Calculate progress to next pin
    if next_pin:
        if current_pin:
            hours_from_last = user_hours - current_pin['hours_required']
            hours_to_next = next_pin['hours_required'] - current_pin['hours_required']
            progress_percentage = (hours_from_last / hours_to_next) * 100 if hours_to_next > 0 else 100
        else:
            progress_percentage = (user_hours / next_pin['hours_required']) * 100 if next_pin['hours_required'] > 0 else 0
    else:
        progress_percentage = 100  # Max level achieved
    
    # Get active volunteer resources
    resources = VolunteerResource.objects.filter(is_active=True).order_by('display_order', 'title')
    resources_serializer = VolunteerResourceSerializer(resources, many=True)
    
    return Response({
        'user_hours': user_hours,
        'current_pin': current_pin,
        'next_pin': next_pin,
        'progress_percentage': round(progress_percentage, 2),
        'milestones': milestones_serializer.data,
        'resources': resources_serializer.data,
        'total_milestones': len(milestones_serializer.data)
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def volunteer_milestones_api(request):
    """
    Get all volunteer pin milestones with achievement status for the current user
    """
    user = request.user
    
    # Get user's volunteer hours
    try:
        user_hours = volunteer_service.get_volunteer_hours(user.student_id) if user.student_id else None
    except (gspread.SpreadsheetNotFound, Exception) as e:
        user_hours = None
    
    if user_hours is None:
        user_hours = 0.0
    
    # Get all milestones
    milestones = VolunteerPinMilestone.objects.all().order_by('hours_required')
    serializer = VolunteerPinMilestoneSerializer(
        milestones, 
        many=True, 
        context={'user_hours': user_hours}
    )
    
    return Response({
        'user_hours': user_hours,
        'milestones': serializer.data
    })


@api_view(['GET'])
def volunteer_resources_api(request):
    """
    Get all active volunteer resources (public endpoint)
    """
    resources = VolunteerResource.objects.filter(is_active=True).order_by('display_order', 'title')
    serializer = VolunteerResourceSerializer(resources, many=True)
    
    return Response({
        'resources': serializer.data
    })
