import datetime
import gspread
import re
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
    "13:05-14:15",
    "14:20-15:30"
]

def get_google_calendar_service():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        settings.GSHEET_CREDENTIALS, 
        scopes=['https://www.googleapis.com/auth/calendar.readonly']
    )
    return build('calendar', 'v3', credentials=creds)

def get_alt_day_event(target_date):
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
    pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*-\s*Block\s*(\d[A-E])'
    matches = re.findall(pattern, description)
    block_times = {}

    if "late start" in description.lower():
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

    return block_times

def _convert_to_sheet_date_format(date_obj):
    """Convert datetime.date to sheet format (e.g., 'Tue, Sep 3')"""
    return date_obj.strftime('%a, %b %-d')

def _parse_iso_date(iso_date):
    """Parse ISO format date (YYYY-MM-DD) to datetime.date object"""
    return datetime.datetime.strptime(iso_date, '%Y-%m-%d').date()

def get_block_order_for_day(iso_date):
    """
    Get block order for a specific date
    :param iso_date: Date in YYYY-MM-DD format
    :return: Dictionary with blocks and times
    """
    date_obj = _parse_iso_date(iso_date)
    sheet_date = _convert_to_sheet_date_format(date_obj)

    existing_schedule = DailySchedule.objects.filter(date=date_obj).first()

    if existing_schedule != None:
        if any([existing_schedule.block_1, existing_schedule.block_2, existing_schedule.block_3, existing_schedule.block_4, existing_schedule.block_5]):
            blocks = [
                existing_schedule.block_1,
                existing_schedule.block_2,
                existing_schedule.block_3,
                existing_schedule.block_4,
                existing_schedule.block_5,
            ]
            times = [
                existing_schedule.block_1_time,
                existing_schedule.block_2_time,
                existing_schedule.block_3_time,
                existing_schedule.block_4_time,
                existing_schedule.block_5_time,
            ]
            
            # Add blocks 6-8 only if they exist
            for block_num in [6, 7, 8]:
                block_value = getattr(existing_schedule, f'block_{block_num}', None)
                time_value = getattr(existing_schedule, f'block_{block_num}_time', None)
                if block_value:
                    blocks.append(block_value)
                    times.append(time_value)
            
            return {
                'blocks': blocks,
                'times': times,
            }
        elif not existing_schedule.is_school and existing_schedule.is_school != None:
            return {
                'blocks': [None, None, None, None, None],
                'times': [None,None, None, None, None],
            }
        

    alt_day_description = get_alt_day_event(date_obj)
    if alt_day_description:
        block_times = extract_block_times_from_description(alt_day_description)
    else:
        block_times = {i + 1: DEFAULT_BLOCK_TIMES[i] for i in range(5)}

    date_column = sheet.col_values(4)[6:]
    rows = sheet.get_all_values()[6:212]

    for i, date_str in enumerate(date_column):
        if date_str.strip() == sheet_date.strip():
            schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
            for block_index in range(5):
                block_field = f'block_{block_index + 1}'
                time_field = f'block_{block_index + 1}_time'
                block_value = rows[i][4 + block_index] if len(rows[i]) > 4 + block_index else None
                time_value = block_times.get(block_index + 1)

                if getattr(schedule, block_field) in [None, ""] and block_value:
                    setattr(schedule, block_field, block_value)

                if getattr(schedule, time_field) in [None, ""] and time_value:
                    setattr(schedule, time_field, time_value)

            # Check if any blocks 1-8 exist to determine if it's a school day
            school_blocks = []
            for block_num in range(1, 9):
                if hasattr(schedule, f'block_{block_num}'):
                    school_blocks.append(getattr(schedule, f'block_{block_num}'))
            
            schedule.is_school = any(school_blocks)
            schedule.save()

            blocks = []
            times = []
            for block_num in range(1, 9):
                if hasattr(schedule, f'block_{block_num}'):
                    block_value = getattr(schedule, f'block_{block_num}')
                    time_value = getattr(schedule, f'block_{block_num}_time')
                    if block_value:  # Only add if block exists and is not null
                        blocks.append(block_value)
                        times.append(time_value)
                elif block_num <= 5:  # Always include blocks 1-5 even if null
                    blocks.append(getattr(schedule, f'block_{block_num}'))
                    times.append(getattr(schedule, f'block_{block_num}_time'))

            return {
                'blocks': blocks,
                'times': times,
            }

    schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
    if created or schedule.is_school is None:
        schedule.is_school = False
    schedule.save()

    return {
        'blocks': [None] * 5,
        'times': [block_times.get(i+1, DEFAULT_BLOCK_TIMES[i] if i < len(DEFAULT_BLOCK_TIMES) else None) for i in range(5)],
    }

def process_schedule_for_user(user, raw_schedule):
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
    Check if ceremonial uniform is required for a specific date
    :param iso_date: Date in YYYY-MM-DD format
    """
    try:
        date_obj = _parse_iso_date(iso_date)
        existing_schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
        if existing_schedule:
            if existing_schedule.ceremonial_uniform:
                return True
            elif existing_schedule.ceremonial_uniform == False:
                return False
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
                existing_schedule.ceremonial_uniform = True
                existing_schedule.save()
                return True

    except HttpError as error:
        print(f"An error occurred: {error}")
        return False

    existing_schedule.ceremonial_uniform = False
    existing_schedule.save()
    return False
