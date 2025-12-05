import datetime
import gspread
import re
from typing import Dict, List, Optional, Any
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from forum.models import UserProfile, DailySchedule

# Initialize Google Sheets client
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(settings.GSHEET_CREDENTIALS, scope)
client = gspread.authorize(creds)

# Open the spreadsheet
sheet = client.open("Copy of 2025-2026 SS Block Order Calendar").sheet1

DEFAULT_BLOCK_TIMES = [
    "8:20-9:30",
    "9:35-10:45",
    "11:05-12:15",
    "1:05-2:15",
    "2:20-3:30"
]

def get_google_calendar_service():
    """
    Initialize and return Google Calendar API service.
    
    Returns:
        Resource: Google Calendar API service object
    """
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        settings.GSHEET_CREDENTIALS, 
        scopes=['https://www.googleapis.com/auth/calendar.readonly']
    )
    return build('calendar', 'v3', credentials=creds)

def get_alt_day_event(target_date):
    """
    Fetch alternate day event details from Google Calendar for a specific date.
    
    Args:
        target_date (datetime.date): The date to check for alternate day events
        
    Returns:
        Optional[str]: Event description if found, None otherwise
    """
    try:
        service = get_google_calendar_service()
        calendar_id = 'nda09oameg390vndlulocmvt07u7c8h4@import.calendar.google.com'
        time_min = datetime.datetime.combine(target_date, datetime.time.min).isoformat() + 'Z'
        time_max = datetime.datetime.combine(target_date, datetime.time.max).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        for event in events_result.get('items', []):
            if event.get('summary', '').lower().startswith("alt day") and event.get('start', {}).get('date'):
                return event.get('description', None)
    except HttpError as error:
        print(f"An error occurred: {error}")
    return None

def extract_block_times_from_description(description):
    """
    Extract block times and detect schedule variations from event description.
    
    Args:
        description (str): Event description containing block time information
        
    Returns:
        tuple: (Dict[int, str], bool, bool) - Block times dict, is_late_start flag, is_early_dismissal flag
    """
    pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*-\s*Block\s*(\d[A-E])'
    matches = re.findall(pattern, description)
    block_times = {}
    
    description_lower = description.lower()
    is_late_start = "late start" in description_lower
    is_early_dismissal = "early dismissal" in description_lower or "early dismiss" in description_lower

    if is_late_start:
        slot = 2
        block_times[1] = None
        for time_range, block_label in matches:
            if 'recess' not in block_label.lower() and 'lunch' not in block_label.lower():
                block_times[slot] = time_range.strip()
                slot += 1
    else:
        slot = 1
        for time_range, block_label in matches:
            if 'recess' not in block_label.lower() and 'lunch' not in block_label.lower():
                block_times[slot] = time_range.strip()
                slot += 1

    return block_times, is_late_start, is_early_dismissal

def _convert_to_sheet_date_format(date_obj):
    """
    Convert datetime.date to sheet format (e.g., 'Tue, Sep 3').
    
    Args:
        date_obj (datetime.date): Date to convert
        
    Returns:
        str: Formatted date string
    """
    return date_obj.strftime('%a, %b %-d')

def _parse_iso_date(iso_date):
    """
    Parse ISO format date (YYYY-MM-DD) to datetime.date object.
    
    Args:
        iso_date (str): ISO formatted date string
        
    Returns:
        datetime.date: Parsed date object
    """
    return datetime.datetime.strptime(iso_date, '%Y-%m-%d').date()

def _is_more_than_week_away(date_obj):
    """
    Check if a date is more than 7 days away from today.
    
    Args:
        date_obj (datetime.date): Date to check
        
    Returns:
        bool: True if date is more than 7 days away, False otherwise
    """
    today = datetime.date.today()
    return abs((date_obj - today).days) > 7

def _parse_time(time_str):
    """
    Parse time string to minutes since midnight.
    
    Args:
        time_str (str): Time string in format "H:MM" or "HH:MM"
        
    Returns:
        int: Minutes since midnight, or None if parsing fails
    """
    if not time_str:
        return None
    try:
        # Extract start time from range (e.g., "8:20-9:30" -> "8:20")
        if '-' in time_str:
            time_str = time_str.split('-')[0].strip()
        parts = time_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError):
        return None

def _detect_late_start(times):
    """
    Detect if schedule is a late start based on first block time.
    
    Args:
        times (List[Optional[str]]): List of time ranges for blocks
        
    Returns:
        bool: True if first block starts after 8:20, False otherwise
    """
    if not times:
        return False
    
    for time_str in times:
        if time_str:  # Find first non-null time
            start_minutes = _parse_time(time_str)
            if start_minutes is not None:
                # 8:20 = 500 minutes since midnight
                return start_minutes > 500
            break
    return False

def _detect_early_dismissal(times):
    """
    Detect if schedule is an early dismissal based on last block end time.
    
    Args:
        times (List[Optional[str]]): List of time ranges for blocks
        
    Returns:
        bool: True if last block ends before 15:30 (3:30 PM), False otherwise
    """
    if not times:
        return False
    
    # Find last non-null time
    last_time = None
    for time_str in reversed(times):
        if time_str:
            last_time = time_str
            break
    
    if not last_time:
        return False
    
    try:
        # Extract end time from range (e.g., "2:20-3:30" -> "3:30")
        if '-' in last_time:
            end_time_str = last_time.split('-')[1].strip()
            parts = end_time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            end_minutes = hours * 60 + minutes
            # 15:30 (3:30 PM) = 930 minutes since midnight
            return end_minutes < 930
    except (ValueError, IndexError):
        pass
    
    return False

def get_block_order_for_day(iso_date):
    """
    Get block order for a specific date.
    
    Args:
        iso_date (str): Date in YYYY-MM-DD format
        
    Returns:
        Dict[str, Any]: Dictionary with keys:
            - blocks (List[Optional[str]]): List of block identifiers (1A, 1B, etc.)
            - times (List[Optional[str]]): List of corresponding time ranges
            - early_dismissal (bool): Whether it's an early dismissal day
            - late_start (bool): Whether it's a late start day
    """
    date_obj = _parse_iso_date(iso_date)
    sheet_date = _convert_to_sheet_date_format(date_obj)
    should_save_to_db = not _is_more_than_week_away(date_obj)

    existing_schedule = DailySchedule.objects.filter(date=date_obj).first()

    if existing_schedule is not None:
        # Use is_school flag to determine if it's a school day
        if existing_schedule.is_school:
            blocks = []
            times = []
            
            # Collect all blocks 1-10 that exist
            for block_num in range(1, 11):
                block_value = getattr(existing_schedule, f'block_{block_num}', None)
                time_value = getattr(existing_schedule, f'block_{block_num}_time', None)
                if block_value:  # Only add blocks that exist
                    blocks.append(block_value)
                    times.append(time_value)
            
            # If no blocks exist at all, treat as having blocks 1-5 as None
            if not blocks:
                blocks = [None] * 5
                times = [None] * 5
            
            # Auto-detect late_start and early_dismissal if not set
            late_start = existing_schedule.late_start
            if late_start is None:
                late_start = _detect_late_start(times)
            
            early_dismissal = existing_schedule.early_dismissal
            if early_dismissal is None:
                early_dismissal = _detect_early_dismissal(times)
            
            return {
                'blocks': blocks,
                'times': times,
                'early_dismissal': early_dismissal or False,
                'late_start': late_start or False,
            }
        elif existing_schedule.is_school == False:
            return {
                'blocks': [None, None, None, None, None],
                'times': [None, None, None, None, None],
                'early_dismissal': False,
                'late_start': False,
            }

    # Fetch from Google Calendar and process
    alt_day_description = get_alt_day_event(date_obj)
    is_late_start = False
    is_early_dismissal = False
    
    if alt_day_description:
        block_times, is_late_start, is_early_dismissal = extract_block_times_from_description(alt_day_description)
    else:
        block_times = {i + 1: DEFAULT_BLOCK_TIMES[i] for i in range(5)}

    date_column = sheet.col_values(4)[6:]
    rows = sheet.get_all_values()[6:212]

    for i, date_str in enumerate(date_column):
        if date_str.strip() == sheet_date.strip():
            if should_save_to_db:
                schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
            else:
                # Don't save to DB, just create a temporary object
                schedule = existing_schedule if existing_schedule else type('obj', (object,), {
                    'block_1': None, 'block_2': None, 'block_3': None, 'block_4': None, 'block_5': None,
                    'block_6': None, 'block_7': None, 'block_8': None, 'block_9': None, 'block_10': None,
                    'block_1_time': None, 'block_2_time': None, 'block_3_time': None, 'block_4_time': None, 'block_5_time': None,
                    'block_6_time': None, 'block_7_time': None, 'block_8_time': None, 'block_9_time': None, 'block_10_time': None,
                    'is_school': None, 'early_dismissal': None, 'late_start': None
                })()
            
            # Process blocks 1-5 from spreadsheet (columns E-I)
            # Additional blocks (6-10) would need to be in later columns or added manually
            for block_index in range(5):
                block_field = f'block_{block_index + 1}'
                time_field = f'block_{block_index + 1}_time'
                block_value = rows[i][4 + block_index] if len(rows[i]) > 4 + block_index else None
                time_value = block_times.get(block_index + 1)

                if getattr(schedule, block_field) in [None, ""] and block_value:
                    # Clean and validate block value - only set if it looks like a valid block
                    if block_value and block_value.strip() and len(block_value.strip()) <= 10:
                        setattr(schedule, block_field, block_value)

                if getattr(schedule, time_field) in [None, ""] and time_value:
                    setattr(schedule, time_field, time_value)

            # Check if any blocks 1-10 exist to determine if it's a school day
            school_blocks = [getattr(schedule, f'block_{block_num}') for block_num in range(1, 11)]
            schedule.is_school = any(school_blocks)
            
            # Collect all blocks and times for detection
            all_times = [getattr(schedule, f'block_{block_num}_time') for block_num in range(1, 11)]
            
            # Auto-detect early dismissal and late start flags from times if not already set
            if schedule.early_dismissal is None:
                schedule.early_dismissal = is_early_dismissal or _detect_early_dismissal(all_times)
            if schedule.late_start is None:
                schedule.late_start = is_late_start or _detect_late_start(all_times)
            
            if should_save_to_db:
                schedule.save()

            # Collect all blocks that exist
            blocks = []
            times = []
            for block_num in range(1, 11):
                block_value = getattr(schedule, f'block_{block_num}')
                time_value = getattr(schedule, f'block_{block_num}_time')
                if block_value:  # Only add if block exists and is not null
                    blocks.append(block_value)
                    times.append(time_value)

            # If no blocks were found, return 5 None blocks
            if not blocks:
                blocks = [None] * 5
                times = [block_times.get(i+1, DEFAULT_BLOCK_TIMES[i] if i < len(DEFAULT_BLOCK_TIMES) else None) for i in range(5)]

            return {
                'blocks': blocks,
                'times': times,
                'early_dismissal': schedule.early_dismissal or False,
                'late_start': schedule.late_start or False,
            }

    # No schedule found in sheet
    if should_save_to_db:
        schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
        if created or schedule.is_school is None:
            schedule.is_school = False
            schedule.early_dismissal = False
            schedule.late_start = False
        schedule.save()

    return {
        'blocks': [None] * 5,
        'times': [block_times.get(i+1, DEFAULT_BLOCK_TIMES[i] if i < len(DEFAULT_BLOCK_TIMES) else None) for i in range(5)],
        'early_dismissal': False,
        'late_start': False,
    }

def process_schedule_for_user(user, raw_schedule):
    """
    Process raw schedule data to include user-specific course information.
    
    Args:
        user (User): The user to process schedule for
        raw_schedule (Dict[str, Any]): Raw schedule data from get_block_order_for_day
        
    Returns:
        List[Union[Dict[str, str], str]]: Processed schedule with course names and times,
            or ["no school"] if no blocks are scheduled
    """
    profile = UserProfile.objects.get(user=user)
    processed_schedule = []

    block_mapping = {
        "1ca": "Advisory",
        '1cap' : "Advisory",
        "1cp": "Advisory",
        "1cap": "Advisory",
        "1c-pa" :"Advisory",
        "1c-ap" : "Advisory",
        "assm": "Assembly",
        "tfr": "Terry Fox Run",
        "g8 assm" : "Grade 8 Assembly ONLY",
        "ss assm" : "Senior School Assembly",
    }

    regular_blocks = ["1a", "1b","1c","1d","1e","2a","2b","2c","2d","2e"]

    if not any(raw_schedule['blocks']):
        return ["no school"]

    for block, time in zip(raw_schedule['blocks'], raw_schedule['times']):
        if not block:
            processed_schedule.append({"block": "No Block", "time": time})
        else:
            normalized = block.strip().lower()
            if normalized in block_mapping:
                processed_schedule.append({"block": block_mapping[normalized], "time": time})
            elif normalized in regular_blocks:
                block_attr = f"block_{normalized.upper()}"
                course = getattr(profile, block_attr, None)
                processed_schedule.append({
                    "block": course.name if course else "Add your courses in profile to unlock this!",
                    "time": time
                })
            else:
                processed_schedule.append({
                    "block": normalized,
                    "time": time,
                })
    return processed_schedule

def is_ceremonial_uniform_required(user, iso_date):
    """
    Check if ceremonial uniform is required for a specific date.
    
    Args:
        user (User): The user making the request (for potential future use)
        iso_date (str): Date in YYYY-MM-DD format
        
    Returns:
        bool: True if ceremonial uniform is required, False otherwise
    """
    try:
        date_obj = _parse_iso_date(iso_date)
        should_save_to_db = not _is_more_than_week_away(date_obj)
        
        if should_save_to_db:
            existing_schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
        else:
            existing_schedule = DailySchedule.objects.filter(date=date_obj).first()
        
        if existing_schedule:
            if existing_schedule.ceremonial_uniform is not None:
                return existing_schedule.ceremonial_uniform
            elif existing_schedule.is_school == False:
                return False

        service = get_google_calendar_service()
        calendar_id = 'nda09oameg390vndlulocmvt07u7c8h4@import.calendar.google.com'
        time_min = datetime.datetime.combine(date_obj, datetime.time.min).isoformat() + 'Z'
        time_max = datetime.datetime.combine(date_obj, datetime.time.max).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        for event in events_result.get('items', []):
            summary = event.get('summary', '').lower()
            description = event.get('description', '').lower()
            
            if 'ceremonial uniform' in summary or 'ceremonial uniform' in description:
                if should_save_to_db and existing_schedule:
                    existing_schedule.ceremonial_uniform = True
                    existing_schedule.save()
                return True

    except HttpError as error:
        print(f"An error occurred: {error}")
        return False

    if should_save_to_db and existing_schedule:
        existing_schedule.ceremonial_uniform = False
        existing_schedule.save()
    return False
