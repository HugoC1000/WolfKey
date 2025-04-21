import datetime
import gspread
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from forum.models import UserProfile, DailySchedule
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httpx
import re

# Initialize Google Sheets client
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(settings.GSHEET_CREDENTIALS, scope)
client = gspread.authorize(creds)

# Open the spreadsheet
sheet = client.open("Copy of 2024-2025 SS Block Order Calendar").sheet1

DEFAULT_BLOCK_TIMES = [
    "8:20-9:30",
    "9:35-10:45",
    "11:05-12:15",
    "13:05-14:15",
    "14:20-15:30"
]

def get_google_calendar_service():
    """
    Initialize the Google Calendar API service.
    """
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        settings.GSHEET_CREDENTIALS, 
        scopes=['https://www.googleapis.com/auth/calendar.readonly']
    )
    return build('calendar', 'v3', credentials=creds)

def get_alt_day_event(target_date):
    """
    Check Google Calendar for an "alt day" all-day event on the given date.
    :param target_date: The date to check (datetime.date object).
    :return: The event description if an "alt day" event exists, otherwise None.
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
    Extract instructional block time ranges from an alt schedule description,
    excluding recess and lunch periods.

    :param description: The event description string.
    :return: A list of instructional block time ranges (e.g., '8:20-9:30').
    """
    # Match pairs of "time range - label"
    pattern = r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*-\s*([^\d]+?)(?=\d|$)'

    matches = re.findall(pattern, description)

    # Filter out blocks labeled 'Recess' or 'Lunch'
    filtered_times = [
        time_range.strip() for time_range, label in matches
        if 'recess' not in label.lower() and 'lunch' not in label.lower()
    ]

    return filtered_times

def get_block_order_for_day(target_date):
    """
    Retrieve the block order for a specific date, using the saved DailySchedule if it exists.
    Date format must match sheet, e.g., "Tue, Sep 3".
    """
    # Convert target_date to a date object
    current_year = datetime.datetime.now().year
    date_obj = datetime.datetime.strptime(f"{target_date}, {current_year}", "%a, %b %d, %Y").date()


    # Check if a DailySchedule already exists for the date
    existing_schedule = DailySchedule.objects.filter(date=date_obj).first()
    if any([existing_schedule.block_1, existing_schedule.block_2, existing_schedule.block_3, existing_schedule.block_4, existing_schedule.block_5]):
        # Use the saved schedule
        return {
            'blocks': [
                existing_schedule.block_1,
                existing_schedule.block_2,
                existing_schedule.block_3,
                existing_schedule.block_4,
                existing_schedule.block_5,
            ],
            'times': [
                existing_schedule.block_1_time,
                existing_schedule.block_2_time,
                existing_schedule.block_3_time,
                existing_schedule.block_4_time,
                existing_schedule.block_5_time,
            ],
        }

    # If no saved schedule exists, proceed to fetch from external sources
    # Check for an "alt day" event in Google Calendar
    alt_day_description = get_alt_day_event(date_obj)

    if alt_day_description:
        # Extract block times from the alt day description
        block_times = extract_block_times_from_description(alt_day_description)
    else:
        # Use default block times
        block_times = DEFAULT_BLOCK_TIMES

    # Fetch the raw block order from Google Sheets
    date_column = sheet.col_values(4)[6:]  # Column D, starting from row 7
    rows = sheet.get_all_values()[6:]      # Skip header rows

    for i, date_str in enumerate(date_column):
        if date_str.strip() == target_date.strip():
            schedule, created = DailySchedule.objects.get_or_create(date=date_obj)

            # Update missing block data
            updated = False
            for block_index in range(5):
                block_field = f'block_{block_index + 1}'
                time_field = f'block_{block_index + 1}_time'

                # Extract value safely
                block_value = rows[i][4 + block_index] if len(rows[i]) > 4 + block_index else None
                time_value = block_times[block_index] if len(block_times) > block_index else None

                # Conditionally update block and time fields if they are not yet set
                if getattr(schedule, block_field) in [None, ""] and block_value:
                    setattr(schedule, block_field, block_value)
                    updated = True

                if getattr(schedule, time_field) in [None, ""] and time_value:
                    setattr(schedule, time_field, time_value)
                    updated = True

            if updated:
                schedule.save()

            return {
                'blocks': [
                    schedule.block_1,
                    schedule.block_2,
                    schedule.block_3,
                    schedule.block_4,
                    schedule.block_5,
                ],
                'times': block_times,
            }

    return {
        'blocks': [None, None, None, None, None],
        'times': block_times,
    }

def interpret_block(block_code):
    if block_code in ("", None):
        return None
    code = block_code.strip().lower()
    if code == "assm":
        return "Assembly"
    if code == "tfr":
        return "Terry Fox Run"
    if code == "1ca":
        return "Academics"
    if code == "1cp":
        return "PEAKS"
    if code == "1cap":
        return "Advisory"
    return block_code

def is_ceremonial_uniform_required(user, target_date):
    """
    Check Google Calendar for a "Ceremonial Uniform Required" all-day event on the given date.
    Date format must match sheet, e.g., "Tue, Sep 3".
    :return: True if ceremonial uniform is required, otherwise False.
    """
    try:
        current_year = datetime.datetime.now().year
        date_obj = datetime.datetime.strptime(f"{target_date}, {current_year}", "%a, %b %d, %Y").date()

        # Check if a DailySchedule already exists for the date
        existing_schedule, created = DailySchedule.objects.get_or_create(date=date_obj)
        if existing_schedule:
            if existing_schedule.ceremonial_uniform:
                return True
            elif existing_schedule.ceremonial_uniform == False:
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
            if event.get('summary', '').lower() == "ceremonial uniform required for senior school students":
                existing_schedule.ceremonial_uniform = True
                existing_schedule.save()
                return True
            

    except HttpError as error:
        print(f"An error occurred: {error}")
        return False

    existing_schedule.ceremonial_uniform = False
    existing_schedule.save()
    return False

def process_schedule_for_user(user, raw_schedule):
    """
    Process the block order for a user and substitute blocks with their courses.
    :param user: User object
    :param raw_schedule: Dictionary containing 'blocks' and 'times'
    :return: List of processed blocks with times
    """
    profile = UserProfile.objects.get(user=user)
    processed_schedule = []

    block_mapping = {
        "1ca": "Academics",
        "1cp": "PEAKS",
        "1cap": "Advisory",
        "assm": "Assembly",
        "tfr": "Terry Fox Run"
    }

    if not any(raw_schedule['blocks']):
        return ["no school"]

    for block, time in zip(raw_schedule['blocks'], raw_schedule['times']):
        if not block:
            processed_schedule.append({"block": "No Block", "time": time})
        else:
            normalized = block.strip().lower()
            if normalized in block_mapping:
                processed_schedule.append({"block": block_mapping[normalized], "time": time})
            else:
                # Try fetching course based on block naming convention
                block_attr = f"block_{normalized.upper()}"
                course = getattr(profile, block_attr, None)
                processed_schedule.append({"block": course.name if course else f"{block}, Add your courses in profile to unlock this!", "time": time})
    return processed_schedule