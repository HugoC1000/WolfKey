"""
Service for accessing WPGA Service Hour Tracking Google Sheet.

This service provides read-only access to the WPGA Service Hour Tracking
spreadsheet to retrieve volunteer hours for students.
"""

from typing import Optional, Dict
import logging
from .google_api_service import google_api_service
import gspread
from googleapiclient.errors import HttpError
from forum.models import VolunteerPinMilestone, VolunteerResource
from forum.services.results import service_error

logger = logging.getLogger(__name__)


def _get_sheet_safe():
    """Return the worksheet or raise the underlying gspread errors.

    This defers fetching the sheet until runtime so import-time failures
    (network / API errors) don't crash Django startup.
    """
    return google_api_service.get_sheet("WPGA Service Hour Tracking", worksheet_index=0)


def get_volunteer_hours(student_number: str) -> Optional[float]:
    """
    Get volunteer hours for a specific student.
    
    Args:
        student_number (str): The student's student number
        
    Returns:
        Optional[float]: The number of volunteer hours, or None if student not found
        
    Raises:
        gspread.SpreadsheetNotFound: If spreadsheet doesn't exist
        gspread.WorksheetNotFound: If worksheet doesn't exist
    """
    try:
        # Lazily get the sheet (avoids import-time network calls)
        sheet = _get_sheet_safe()
        # Get all values at once (single API call)
        all_values = sheet.get_all_values()
        
        # Normalize the student number for comparison
        student_number_normalized = str(student_number).strip()
        
        # Skip the header row (index 0) and search for student
        for row in all_values[1:]:
            if len(row) >= 3:  # Ensure row has at least columns A, B, C
                row_student_number = str(row[1]).strip()  # Column B (index 1)
                
                if row_student_number == student_number_normalized:
                    # Found the student, get their hours from column C (index 2)
                    hours_value = str(row[2]).strip() if len(row) > 2 else ""
                    
                    try:
                        return float(hours_value) if hours_value else 0.0
                    except (ValueError, AttributeError):
                        return 0.0
        
        # Student not found
        return None
        
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        # Propagate spreadsheet/worksheet not found so callers can handle explicitly
        raise
    except HttpError as e:
        # Google API low-level error — log and return None
        print(f"Error retrieving volunteer hours: {e.__dict__}")
        return None
    except Exception as e:
        print(f"Error retrieving volunteer hours: {str(e)}")
        return None


def get_all_service_hours() -> Dict[str, float]:
    """
    Get all service hours as a dictionary mapping student numbers to hours.
    
    Returns:
        dict: Dictionary with student numbers as keys and service hours as values
        
    Raises:
        gspread.SpreadsheetNotFound: If spreadsheet doesn't exist
        gspread.WorksheetNotFound: If worksheet doesn't exist
    """
    try:
        sheet = _get_sheet_safe()
        # Get all values at once (single API call)
        all_values = sheet.get_all_values()
        
        result = {}
        
        # Skip the header row (index 0) and process data rows
        for row in all_values[1:]:
            if len(row) >= 3:  # Ensure row has at least columns A, B, C
                student_number = str(row[1]).strip()  # Column B (index 1)
                hours_value = str(row[2]).strip() if len(row) > 2 else ""  # Column C (index 2)
                
                if student_number:  # Only add if student number is not empty
                    try:
                        hours = float(hours_value) if hours_value else 0.0
                        result[student_number] = hours
                    except (ValueError, AttributeError):
                        result[student_number] = 0.0
        
        return result
        
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound):
        raise
    except HttpError as e:
        print(f"Error retrieving all service hours: {e.__dict__}")
        return {}
    except Exception as e:
        print(f"Error retrieving all service hours: {str(e)}")
        return {}


def clear_cache():
    """
    Clear the cached Google Sheet data for WPGA Service Hours.
    This forces a fresh fetch on the next request.
    """
    google_api_service.clear_sheet_cache("WPGA Service Hour Tracking")


def is_volunteer_admin(user):
    return user.is_authenticated and (user.is_staff or user.volunteer_coordinator)


def get_volunteer_admin_data():
    return {
        'milestones': VolunteerPinMilestone.objects.all().order_by('hours_required'),
        'resources': VolunteerResource.objects.all().order_by('display_order', 'title'),
    }


def get_volunteer_page_data(user):
    try:
        user_hours = get_volunteer_hours(user.student_id) if user.student_id else None
    except Exception:
        logger.exception('Unable to load volunteer hours')
        user_hours = None
    user_hours = user_hours if user_hours is not None else 0.0

    pin_milestones = [
        {
            'name': milestone.name,
            'hours': milestone.hours_required,
            'achieved': user_hours >= milestone.hours_required,
            'progress': min(100, user_hours / milestone.hours_required * 100)
            if milestone.hours_required else 100,
            'has_other_requirements': milestone.has_other_requirements,
        }
        for milestone in VolunteerPinMilestone.objects.all().order_by('hours_required')
    ]
    current_pin = next((pin for pin in reversed(pin_milestones) if pin['achieved']), None)
    next_pin = next((pin for pin in pin_milestones if not pin['achieved']), None)
    if next_pin:
        previous_hours = current_pin['hours'] if current_pin else 0
        span = next_pin['hours'] - previous_hours
        progress_percentage = (user_hours - previous_hours) / span * 100 if span else 100
    else:
        progress_percentage = 100
    return {
        'user_hours': user_hours,
        'current_pin': current_pin,
        'next_pin': next_pin,
        'progress_percentage': progress_percentage,
        'pin_milestones': pin_milestones,
        'resources': VolunteerResource.objects.filter(is_active=True).order_by('display_order', 'title'),
        'total_milestones': len(pin_milestones),
    }


def save_milestone(user, data, milestone_id=None):
    if not is_volunteer_admin(user):
        return service_error('Permission denied', 403)
    name = (data.get('name') or '').strip()
    raw_hours = (data.get('hours_required') or '').strip()
    if not name or not raw_hours:
        return service_error('Name and hours required are mandatory fields.')
    try:
        hours_required = int(raw_hours)
        if hours_required < 0:
            raise ValueError
    except ValueError:
        return service_error('Invalid hours or order value. Please enter valid numbers.')
    milestone = VolunteerPinMilestone.objects.filter(id=milestone_id).first() if milestone_id else VolunteerPinMilestone()
    if milestone is None:
        return service_error('Milestone not found', 404)
    milestone.name = name
    milestone.hours_required = hours_required
    milestone.has_other_requirements = data.get('has_other_requirements') == 'on'
    milestone.save()
    action = 'updated' if milestone_id else 'created'
    return {'message': f'Milestone "{milestone.name}" {action} successfully!'}


def delete_milestone(user, milestone_id):
    if not is_volunteer_admin(user):
        return service_error('Permission denied', 403)
    milestone = VolunteerPinMilestone.objects.filter(id=milestone_id).first()
    if milestone is None:
        return service_error('Milestone not found', 404)
    name = milestone.name
    milestone.delete()
    return {'message': f'Milestone "{name}" deleted successfully!'}


def save_resource(user, data, resource_id=None):
    if not is_volunteer_admin(user):
        return service_error('Permission denied', 403)
    title = (data.get('title') or '').strip()
    url = (data.get('url') or '').strip()
    if not title or not url:
        return service_error('Title and URL are mandatory fields.')
    try:
        display_order = int((data.get('display_order', '0') or '0').strip())
        if display_order < 0:
            raise ValueError
    except ValueError:
        return service_error('Invalid display order value. Please enter a valid number.')
    resource = VolunteerResource.objects.filter(id=resource_id).first() if resource_id else VolunteerResource()
    if resource is None:
        return service_error('Resource not found', 404)
    resource.title = title
    resource.url = url
    resource.description = (data.get('description') or '').strip()
    resource.display_order = display_order
    resource.is_active = data.get('is_active') == 'on'
    resource.save()
    action = 'updated' if resource_id else 'created'
    return {'message': f'Resource "{resource.title}" {action} successfully!'}


def delete_resource(user, resource_id):
    if not is_volunteer_admin(user):
        return service_error('Permission denied', 403)
    resource = VolunteerResource.objects.filter(id=resource_id).first()
    if resource is None:
        return service_error('Resource not found', 404)
    title = resource.title
    resource.delete()
    return {'message': f'Resource "{title}" deleted successfully!'}
