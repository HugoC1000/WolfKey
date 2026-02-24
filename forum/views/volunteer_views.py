from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from forum.services import volunteer_service
from forum.models import User, VolunteerPinMilestone, VolunteerResource
import gspread


@login_required
def volunteer_hours_page(request):
    """
    Display the volunteer hours page with user stats and milestones.
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
    
    # Format milestones for template
    pin_milestones = []
    for milestone in db_milestones:
        pin_milestones.append({
            'name': milestone.name,
            'hours': milestone.hours_required,
            'achieved': user_hours >= milestone.hours_required,
            'progress': min(100, (user_hours / milestone.hours_required) * 100) if user_hours < milestone.hours_required else 100
        })
    
    # Calculate current pin and progress
    current_pin = None
    next_pin = None
    progress_percentage = 0
    
    for pin in pin_milestones:
        if user_hours >= pin['hours']:
            current_pin = pin
        elif next_pin is None and user_hours < pin['hours']:
            next_pin = pin
    
    # Calculate progress to next pin
    if next_pin:
        if current_pin:
            hours_from_last = user_hours - current_pin['hours']
            hours_to_next = next_pin['hours'] - current_pin['hours']
            progress_percentage = (hours_from_last / hours_to_next) * 100
        else:
            progress_percentage = (user_hours / next_pin['hours']) * 100
    else:
        progress_percentage = 100  # Max level achieved
    
    # Get volunteer resources
    resources = VolunteerResource.objects.filter(is_active=True).order_by('display_order', 'title')
    
    context = {
        'user_hours': user_hours,
        'current_pin': current_pin,
        'next_pin': next_pin,
        'progress_percentage': progress_percentage,
        'pin_milestones': pin_milestones,
        'resources': resources,
        'total_milestones': len(pin_milestones),
    }
    
    return render(request, 'forum/volunteer_hours.html', context)
