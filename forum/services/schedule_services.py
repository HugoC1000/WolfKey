import datetime
import re
import time
import logging
import json
import os
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any, Tuple
from django.conf import settings
from googleapiclient.errors import HttpError
from forum.models import UserProfile, DailySchedule
from forum.services.google_api_service import google_api_service

logger = logging.getLogger(__name__)

# Sheet constants
SHEET_NAME = "Copy of 2026-2027 SS Block Order Calendar"
SHEET_HEADER_ROWS = 6  # Number of header rows to skip
SHEET_DATE_COLUMN = 4  # Column D (1-indexed in sheet, 4 in API)
SHEET_BLOCK_START_COLUMN = 5  # Column E (1-indexed in sheet, 5 in API) - blocks 1-5 start here
SHEET_MAX_ROWS = 212  # Maximum data rows in sheet
MAX_BLOCKS_IN_SHEET = 5  # Only blocks 1-5 are in spreadsheet

# Cache file path for date-to-row mappings
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(BASE_DIR, 'schedule_cache.json')

# Calendar ID for alternate day events
ALT_DAY_CALENDAR_ID = 'nda09oameg390vndlulocmvt07u7c8h4@import.calendar.google.com'

# Remote sheet and in-memory data are loaded only when schedule code needs them.
_sheet = None
_sheet_data = None
_sheet_row_cache = None


def _get_schedule_sheet():
    """Open the remote spreadsheet on first use instead of during Django startup."""
    global _sheet
    if _sheet is None:
        _sheet = google_api_service.get_sheet(SHEET_NAME, worksheet_index=0)
    return _sheet

DEFAULT_BLOCK_TIMES = [
    "8:20-9:30",
    "9:35-10:45",
    "11:05-12:15",
    "1:05-2:15",
    "2:20-3:30"
]

def rebuild_date_row_cache():
    """
    Rebuild the schedule date-to-row number cache and load sheet data into memory.
    Run this explicitly when the source schedule changes.
    
    Returns:
        int: Number of dates cached
    """
    global _sheet_data, _sheet_row_cache
    
    logger.info("[rebuild_date_row_cache] Starting cache rebuild...")
    
    try:
        sheet = _get_schedule_sheet()
        # Load all sheet data at once
        all_rows = sheet.get_all_values()[SHEET_HEADER_ROWS:SHEET_MAX_ROWS]
        date_column = sheet.col_values(SHEET_DATE_COLUMN)[SHEET_HEADER_ROWS:]
        
        cache = {}
        sheet_data = {}
        
        for i, date_str in enumerate(date_column):
            if date_str.strip():
                row_key = date_str.strip()
                row_number = i + SHEET_HEADER_ROWS
                cache[row_key] = row_number
                
                # Cache the actual row data too
                if i < len(all_rows):
                    sheet_data[row_key] = all_rows[i]
        
        # Write cache to file for persistence
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
        
        # Store in memory for this session
        _sheet_data = sheet_data
        _sheet_row_cache = cache
        
        logger.info(f"[rebuild_date_row_cache] Cache rebuilt with {len(cache)} dates")
        return len(cache)
        
    except Exception as e:
        logger.error(f"[rebuild_date_row_cache] Error rebuilding cache: {str(e)}")
        raise

def load_row_from_cache(sheet_date):
    """
    Load row number for a specific date from the in-memory cache.
    Falls back to file cache if needed.
    
    Args:
        sheet_date (str): Date in sheet format (e.g., 'Tue, Sep 3')
        
    Returns:
        Optional[int]: Row number if found in cache, None otherwise
    """
    global _sheet_row_cache
    
    sheet_date = sheet_date.strip()
    
    # Try in-memory cache first
    if _sheet_row_cache and sheet_date in _sheet_row_cache:
        return _sheet_row_cache[sheet_date]
    
    # Fall back to file cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                return cache.get(sheet_date)
    except Exception as e:
        logger.warning(f"[load_row_from_cache] Error loading file cache: {str(e)}")
    
    return None

def get_sheet_row_data(sheet_date) -> Optional[List[str]]:
    """
    Get the actual row data for a date from in-memory cache.
    
    Args:
        sheet_date (str): Date in sheet format (e.g., 'Tue, Sep 3')
        
    Returns:
        Optional[List[str]]: Row data if found, None otherwise
    """
    global _sheet_data
    
    sheet_date = sheet_date.strip()
    
    if _sheet_data and sheet_date in _sheet_data:
        return _sheet_data[sheet_date]
    
    # The file cache is ignored by Git, so a new deployment may have no row map.
    # Look up the date in the sheet instead of treating every day as no school.
    sheet = _get_schedule_sheet()
    row_number = load_row_from_cache(sheet_date)
    if row_number is None:
        dates = sheet.col_values(SHEET_DATE_COLUMN)[SHEET_HEADER_ROWS:SHEET_MAX_ROWS]
        row_index = next((i for i, value in enumerate(dates) if value.strip() == sheet_date), None)
    else:
        row_index = row_number - SHEET_HEADER_ROWS

    if row_index is not None:
        all_rows = sheet.get_all_values()[SHEET_HEADER_ROWS:SHEET_MAX_ROWS]
        if row_index < len(all_rows):
            if _sheet_data is None:
                _sheet_data = {}
            _sheet_data[sheet_date] = all_rows[row_index]
            return all_rows[row_index]

    return None

def get_calendar_events_for_day(target_date, calendar_context=None, max_retries=3):
    """Fetch a day's calendar events once and reuse them within a request."""
    cache_key = target_date.isoformat()
    if calendar_context is not None and cache_key in calendar_context:
        return calendar_context[cache_key]

    for attempt in range(max_retries):
        try:
            service = google_api_service.get_calendar_service()
            school_timezone = ZoneInfo(settings.TIME_ZONE)
            time_min = datetime.datetime.combine(
                target_date, datetime.time.min, tzinfo=school_timezone
            ).isoformat()
            time_max = datetime.datetime.combine(
                target_date + datetime.timedelta(days=1), datetime.time.min,
                tzinfo=school_timezone
            ).isoformat()

            logger.debug(f"[get_calendar_events_for_day] Attempt {attempt + 1}/{max_retries} for date: {target_date}")
            
            events_result = service.events().list(
                calendarId=ALT_DAY_CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            if calendar_context is not None:
                calendar_context[cache_key] = events
            return events
            
        except (HttpError, ConnectionError, BrokenPipeError, IOError, TimeoutError) as error:
            logger.warning(f"[get_calendar_events_for_day] Attempt {attempt + 1} failed: {type(error).__name__}: {str(error)}")
            
            if attempt < max_retries - 1:
                wait_time = 2.0 * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                logger.info(f"[get_calendar_events_for_day] Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"[get_calendar_events_for_day] All attempts failed for {target_date}. Using defaults.")
                if calendar_context is not None:
                    calendar_context[cache_key] = None
                return None

    return None

def get_alt_day_event(calendar_events, target_date):
    """Return the alternate-day event starting on the requested school date."""
    for event in calendar_events or []:
        if (
            event.get('summary', '').lower().startswith('alt day')
            and event.get('start', {}).get('date') == target_date.isoformat()
        ):
            return event
    return None


def _events_require_ceremonial_uniform(calendar_events):
    return any(
        'ceremonial uniform' in event.get('summary', '').lower()
        or 'ceremonial uniform' in event.get('description', '').lower()
        for event in calendar_events or []
    )

def extract_block_times_from_description(description):
    """
    Extract block times from Google Calendar event description.
    Returns times in order they appear, mapped to block positions.
    
    Args:
        description (str): Event description with time ranges
        
    Returns:
        List[str]: Time ranges in order (e.g., ['8:20-9:15', '9:20-10:15', ...])
    """
    pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*-\s*Block'
    matches = re.findall(pattern, description)
    return [m.strip() for m in matches]

def _detect_flags_from_times(time_ranges: List[str]) -> Tuple[bool, bool]:
    """
    Detect late_start and early_dismissal flags from a list of time ranges.
    
    Args:
        time_ranges (List[str]): Time ranges (e.g., ['8:20-9:30', '9:35-10:45', ...])
        
    Returns:
        Tuple of (is_late_start, is_early_dismissal)
    """
    is_late_start = False
    is_early_dismissal = False
    
    if time_ranges:
        # Check first block time
        try:
            first_time = time_ranges[0].split('-')[0].strip()
            hours, minutes = map(int, first_time.split(':'))
            first_minutes = hours * 60 + minutes
            # 8:20 = 500 minutes
            if first_minutes > 500:
                is_late_start = True
        except (ValueError, IndexError):
            pass
        
        # Check last block time
        try:
            last_time = time_ranges[-1].split('-')[1].strip()
            hours, minutes = map(int, last_time.split(':'))
            # Convert to 24-hour if PM
            if 1 <= hours <= 7:
                hours += 12
            last_minutes = hours * 60 + minutes
            # 15:30 (3:30 PM) = 930 minutes
            if last_minutes < 930:
                is_early_dismissal = True
        except (ValueError, IndexError):
            pass
    
    return is_late_start, is_early_dismissal

def _get_calendar_block_times_and_flags(alt_day_description: str) -> Tuple[List[str], bool, bool]:
    """
    Extract block times from calendar and detect early dismissal/late start.
    
    Args:
        alt_day_description (str): Calendar event description
        
    Returns:
        Tuple of (time_ranges, is_late_start, is_early_dismissal)
    """
    time_ranges = extract_block_times_from_description(alt_day_description)
    is_late_start, is_early_dismissal = _detect_flags_from_times(time_ranges)
    return time_ranges, is_late_start, is_early_dismissal

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

def _detect_late_start(block_names: List[Optional[str]]) -> bool:
    """
    Detect if schedule is a late start (first block slot is None/empty).
    
    Args:
        block_names (List[Optional[str]]): List of block names from spreadsheet
        
    Returns:
        bool: True if first block is None (late start), False otherwise
    """
    return block_names and len(block_names) > 0 and block_names[0] is None

def _detect_early_dismissal(block_names: List[Optional[str]]) -> bool:
    """
    Detect if schedule is an early dismissal (blocks end before normal time).
    This is now detected from calendar times, not block names.
    Kept for compatibility but should use calendar-detected flag instead.
    
    Args:
        block_names (List[Optional[str]]): List of block names from spreadsheet
        
    Returns:
        bool: False (detection now happens from calendar times)
    """
    return False

def _extract_and_save_blocks(
    date_obj: datetime.date,
    spreadsheet_blocks: List[Optional[str]],
    calendar_times: List[str],
    is_late_start: bool,
    is_early_dismissal: bool,
    should_save_to_db: bool
) -> Tuple[List[Optional[str]], List[Optional[str]], bool, bool]:
    """
    Merge spreadsheet block names with calendar times and save to database.
    
    Args:
        date_obj: The date for this schedule
        spreadsheet_blocks: Block names from spreadsheet (e.g., ['2A', '2B', '2D', ...])
        calendar_times: Times from calendar (e.g., ['8:20-9:15', '9:20-10:15', ...])
        is_late_start: Flag detected from calendar times
        is_early_dismissal: Flag detected from calendar times
        should_save_to_db: Whether to persist to database
        
    Returns:
        Tuple of (blocks, times, early_dismissal, late_start)
    """
    if should_save_to_db:
        schedule, _ = DailySchedule.objects.get_or_create(date=date_obj)
    else:
        schedule = type('obj', (object,), {f'block_{i}': None for i in range(1, 11)} | {f'block_{i}_time': None for i in range(1, 11)} | {'is_school': None, 'early_dismissal': None, 'late_start': None})()
    
    # Map block names to times
    for idx, block_name in enumerate(spreadsheet_blocks):
        if idx < MAX_BLOCKS_IN_SHEET:
            block_field = f'block_{idx + 1}'
            time_field = f'block_{idx + 1}_time'
            
            if block_name:
                setattr(schedule, block_field, block_name)
            
            time_value = calendar_times[idx] if idx < len(calendar_times) else None
            if time_value:
                setattr(schedule, time_field, time_value)
    
    # Mark as school day
    schedule.is_school = any(spreadsheet_blocks)
    schedule.early_dismissal = is_early_dismissal
    schedule.late_start = is_late_start
    
    if should_save_to_db:
        schedule.calendar_verified = True
        schedule.save()
    
    # Format for return
    blocks = [b for b in spreadsheet_blocks if b]
    times = [calendar_times[i] for i, b in enumerate(spreadsheet_blocks) if b and i < len(calendar_times)]
    
    # Pad with None if missing times
    if len(times) < len(blocks):
        times.extend([None] * (len(blocks) - len(times)))
    
    if not blocks:
        blocks = [None] * MAX_BLOCKS_IN_SHEET
        times = calendar_times if calendar_times else DEFAULT_BLOCK_TIMES
    
    return blocks, times, is_early_dismissal, is_late_start

def get_block_order_for_day(iso_date, calendar_context=None):
    """
    Get block order for a specific date.
    
    Flow:
    1. Check database cache
    2. Fetch spreadsheet row (authority on school day + block names)
    3. If no blocks in spreadsheet → return "no school"
    4. If blocks exist → fetch calendar for times
    5. Merge + save to DB
    
    Args:
        iso_date (str): Date in YYYY-MM-DD format
        
    Returns:
        Dict[str, Any]: Dictionary with keys:
            - blocks (List[Optional[str]]): List of block identifiers (1A, 1B, etc.)
            - times (List[Optional[str]]): List of corresponding time ranges
            - early_dismissal (bool): Whether it's an early dismissal day
            - late_start (bool): Whether it's a late start day
    """
    try:
        logger.debug(f"[get_block_order_for_day] Starting for date: {iso_date}")
        
        date_obj = _parse_iso_date(iso_date)
        sheet_date = _convert_to_sheet_date_format(date_obj)
        should_save_to_db = not _is_more_than_week_away(date_obj)

        # Step 1: Check database cache
        existing_schedule = DailySchedule.objects.filter(date=date_obj).first()
        if existing_schedule and existing_schedule.is_school is not None and (
            not existing_schedule.is_school
            or existing_schedule.calendar_verified
        ):
            blocks = []
            times = []
            for block_num in range(1, 11):
                block_value = getattr(existing_schedule, f'block_{block_num}', None)
                time_value = getattr(existing_schedule, f'block_{block_num}_time', None)
                if block_value:
                    blocks.append(block_value)
                    times.append(time_value)
            
            if not blocks:
                blocks = [None] * MAX_BLOCKS_IN_SHEET
                times = [None] * MAX_BLOCKS_IN_SHEET
            
            return {
                'blocks': blocks,
                'times': times,
                'early_dismissal': existing_schedule.early_dismissal or False,
                'late_start': existing_schedule.late_start or False,
            }

        # Step 2: Fetch spreadsheet row (authority on school day + block names)
        row_data = get_sheet_row_data(sheet_date)
        
        if not row_data:
            logger.debug(f"[get_block_order_for_day] No spreadsheet data found for {sheet_date}")
            # Save non-school day
            if should_save_to_db:
                schedule, _ = DailySchedule.objects.get_or_create(date=date_obj)
                schedule.is_school = False
                schedule.early_dismissal = False
                schedule.late_start = False
                schedule.save()
            
            return {
                'blocks': [None] * MAX_BLOCKS_IN_SHEET,
                'times': [None] * MAX_BLOCKS_IN_SHEET,
                'early_dismissal': False,
                'late_start': False,
            }

        # Step 3: Extract block names from spreadsheet row
        spreadsheet_blocks = []
        for block_index in range(MAX_BLOCKS_IN_SHEET):
            col_idx = SHEET_BLOCK_START_COLUMN - 1 + block_index
            block_value = row_data[col_idx] if col_idx < len(row_data) else None
            
            if block_value and block_value.strip():
                spreadsheet_blocks.append(block_value.strip())
            else:
                spreadsheet_blocks.append(None)
        
        # Step 4: If no blocks in spreadsheet, it's not a school day
        if not any(spreadsheet_blocks):
            logger.debug(f"[get_block_order_for_day] No blocks found in spreadsheet for {sheet_date}")
            if should_save_to_db:
                schedule, _ = DailySchedule.objects.get_or_create(date=date_obj)
                schedule.is_school = False
                schedule.early_dismissal = False
                schedule.late_start = False
                schedule.save()
            
            return {
                'blocks': [None] * MAX_BLOCKS_IN_SHEET,
                'times': [None] * MAX_BLOCKS_IN_SHEET,
                'early_dismissal': False,
                'late_start': False,
            }

        # Step 5: Fetch calendar for block times
        logger.debug(f"[get_block_order_for_day] Fetching calendar event for {date_obj}")
        
        calendar_events = get_calendar_events_for_day(date_obj, calendar_context)
        alt_day_event = get_alt_day_event(calendar_events, date_obj)
        alt_day_description = alt_day_event.get('description') if alt_day_event else None
        alt_day_summary = alt_day_event.get('summary') if alt_day_event else None
        
        calendar_times = []
        is_late_start = False
        is_early_dismissal = False
        
        if alt_day_description:  # Only if description exists and is not None
            logger.debug(f"[get_block_order_for_day] Alt day event found with description, extracting times")
            calendar_times, is_late_start, is_early_dismissal = _get_calendar_block_times_and_flags(alt_day_description)
        else:
            # Use default times for detection
            calendar_times = list(DEFAULT_BLOCK_TIMES[:len(spreadsheet_blocks)])
            # Still run detection on default times
            if calendar_times:
                is_late_start, is_early_dismissal = _detect_flags_from_times(calendar_times)
            
            # Check summary for Early Dismissal flag if description missing
            if alt_day_summary and "early dismissal" in alt_day_summary.lower():
                is_early_dismissal = True
        
        # Step 6: Fallback to default times if calendar incomplete or missing
        while len(calendar_times) < len(spreadsheet_blocks):
            calendar_times.append(DEFAULT_BLOCK_TIMES[len(calendar_times)] if len(calendar_times) < len(DEFAULT_BLOCK_TIMES) else None)
        
        # Step 7: Merge and save
        blocks, times, early_dismissal, late_start = _extract_and_save_blocks(
            date_obj=date_obj,
            spreadsheet_blocks=spreadsheet_blocks,
            calendar_times=calendar_times,
            is_late_start=is_late_start,
            is_early_dismissal=is_early_dismissal,
            should_save_to_db=should_save_to_db and calendar_events is not None
        )

        if should_save_to_db and calendar_events is not None:
            DailySchedule.objects.filter(date=date_obj).update(
                ceremonial_uniform=_events_require_ceremonial_uniform(calendar_events)
            )

        return {
            'blocks': blocks,
            'times': times,
            'early_dismissal': early_dismissal,
            'late_start': late_start,
        }
    except Exception as e:
        logger.error(f"[get_block_order_for_day] Error for {iso_date}: {e}")
        raise

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
        "1c" : "Advisory"
    }

    regular_blocks = ["1a", "1b","1d","1e","2a","2b","2c","2d","2e"]

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
                    "block": course.name if course else "Add your courses in profile!",
                    "time": time
                })
            else:
                processed_schedule.append({
                    "block": normalized,
                    "time": time,
                })
    return processed_schedule

def is_ceremonial_uniform_required(iso_date, calendar_context=None):
    """
    Check if ceremonial uniform is required for a specific date.
    Includes retry logic with exponential backoff for transient errors.
    
    Args:
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
            if (existing_schedule.is_school is False or existing_schedule.calendar_verified) and existing_schedule.ceremonial_uniform is not None:
                return existing_schedule.ceremonial_uniform
            elif existing_schedule.is_school == False:
                return False

        calendar_events = get_calendar_events_for_day(date_obj, calendar_context)
        if calendar_events is None:
            return False
        is_required = _events_require_ceremonial_uniform(calendar_events)
        logger.debug(
            f"[is_ceremonial_uniform_required] Ceremonial uniform "
            f"{'found' if is_required else 'not found'} for {iso_date}"
        )
        if should_save_to_db and existing_schedule:
            existing_schedule.ceremonial_uniform = is_required
            existing_schedule.save(update_fields=['ceremonial_uniform'])
        return is_required

    except Exception as error:
        logger.error(f"[is_ceremonial_uniform_required] Critical error: {type(error).__name__}: {str(error)}")
        return False


def get_user_blocks_for_viewer(viewer, user_id):
    """Load a timetable only when both users' privacy settings permit it."""
    from forum.services.results import service_error

    target_profile = UserProfile.objects.select_related('user').filter(user_id=user_id).first()
    if target_profile is None:
        return service_error('User or profile not found', 404)
    viewer_profile = getattr(viewer, 'userprofile', None)
    if viewer.id != target_profile.user_id and (
        not viewer_profile or not viewer_profile.allow_schedule_comparison
    ):
        return service_error('Enable schedule comparison to compare schedules', 403)
    if not target_profile.allow_schedule_comparison:
        return service_error('This user has disabled schedule comparison', 403)
    return {'profile': target_profile}
