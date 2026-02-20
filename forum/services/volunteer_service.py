"""
Service for accessing WPGA Service Hour Tracking Google Sheet.

This service provides read-only access to the WPGA Service Hour Tracking
spreadsheet to retrieve volunteer hours for students.
"""

from typing import Optional, Dict
from .google_api_service import google_api_service
import gspread

# Open the spreadsheet using the common Google API service
# The worksheet reference is cached by google_api_service
sheet = google_api_service.get_sheet("WPGA Service Hour Tracking", worksheet_index=0)


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
        
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound) as e:
        raise
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
        
    except (gspread.SpreadsheetNotFound, gspread.WorksheetNotFound) as e:
        raise
    except Exception as e:
        print(f"Error retrieving all service hours: {str(e)}")
        return {}


def clear_cache():
    """
    Clear the cached Google Sheet data for WPGA Service Hours.
    This forces a fresh fetch on the next request.
    """
    google_api_service.clear_sheet_cache("WPGA Service Hour Tracking")
