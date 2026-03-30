"""
Common service for accessing Google APIs (Sheets and Calendar).

This service handles credential initialization and provides read-only
access to Google Sheets and Google Calendar APIs. It includes caching
for Google Sheets to improve performance.
"""

import gspread
from django.conf import settings
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from typing import Optional, Dict, Any
import httplib2
from googleapiclient.errors import HttpError
from gspread.exceptions import APIError
import time


class GoogleAPIService:
    """
    Singleton service for managing Google API access.
    Provides read-only access to Google Sheets and Google Calendar.
    """
    
    _instance = None
    _sheets_client = None
    _calendar_service = None
    _cached_sheets: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleAPIService, cls).__new__(cls)
        return cls._instance
    
    def _initialize_sheets_client(self):
        """
        Initialize and cache the Google Sheets client.
        
        Returns:
            gspread.Client: Authorized Google Sheets client
        """
        if self._sheets_client is None:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                settings.GSHEET_CREDENTIALS, 
                scope
            )
            self._sheets_client = gspread.authorize(creds)
        return self._sheets_client
    
    def _initialize_calendar_service(self):
        """
        Initialize and cache the Google Calendar API service.
        
        Returns:
            Resource: Google Calendar API service object
        """
        if self._calendar_service is None:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                settings.GSHEET_CREDENTIALS,
                scopes=['https://www.googleapis.com/auth/calendar.readonly']
            )
            
            # Create httplib2 HTTP object with 30 second timeout
            http = httplib2.Http(timeout=30)
            authorized_http = creds.authorize(http)
            
            # Build calendar service with authorized HTTP client
            self._calendar_service = build('calendar', 'v3', http=authorized_http)
        return self._calendar_service

    def _with_backoff(self, func, *args, **kwargs):
        """Run `func` with simple exponential backoff on transient errors.

        Retries HttpError, gspread APIError and OSError (network issues).
        """
        max_attempts = 4
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except (HttpError, APIError, OSError) as e:
                if attempt == max_attempts:
                    raise
                print(f"Google API call failed (attempt {attempt}): {e}; retrying in {delay}s")
                time.sleep(delay)
                delay *= 2
    
    def get_sheet(self, spreadsheet_name: str, worksheet_index: int = 0):
        """
        Get a worksheet from a Google Spreadsheet by name.
        Caches the worksheet for subsequent requests.
        
        Args:
            spreadsheet_name (str): Name of the spreadsheet to open
            worksheet_index (int): Index of the worksheet (default: 0 for first sheet)
            
        Returns:
            gspread.Worksheet: The requested worksheet
            
        Raises:
            gspread.SpreadsheetNotFound: If spreadsheet doesn't exist
            gspread.WorksheetNotFound: If worksheet doesn't exist
        """
        cache_key = f"{spreadsheet_name}:{worksheet_index}"
        
        if cache_key not in self._cached_sheets:
            client = self._initialize_sheets_client()
            # Wrap open and get_worksheet with backoff to handle transient errors
            spreadsheet = self._with_backoff(client.open, spreadsheet_name)
            worksheet = self._with_backoff(spreadsheet.get_worksheet, worksheet_index)
            self._cached_sheets[cache_key] = worksheet
        
        return self._cached_sheets[cache_key]
    
    def get_sheet_by_key(self, spreadsheet_key: str, worksheet_index: int = 0):
        """
        Get a worksheet from a Google Spreadsheet by its key/ID.
        Caches the worksheet for subsequent requests.
        
        Args:
            spreadsheet_key (str): The spreadsheet key/ID from the URL
            worksheet_index (int): Index of the worksheet (default: 0 for first sheet)
            
        Returns:
            gspread.Worksheet: The requested worksheet
            
        Raises:
            gspread.SpreadsheetNotFound: If spreadsheet doesn't exist
            gspread.WorksheetNotFound: If worksheet doesn't exist
        """
        cache_key = f"key:{spreadsheet_key}:{worksheet_index}"
        
        if cache_key not in self._cached_sheets:
            client = self._initialize_sheets_client()
            # Wrap open_by_key and get_worksheet with backoff to handle transient errors
            spreadsheet = self._with_backoff(client.open_by_key, spreadsheet_key)
            worksheet = self._with_backoff(spreadsheet.get_worksheet, worksheet_index)
            self._cached_sheets[cache_key] = worksheet
        
        return self._cached_sheets[cache_key]
    
    def get_calendar_service(self):
        """
        Get the Google Calendar API service for read-only operations.
        
        Returns:
            Resource: Google Calendar API service object
        """
        return self._initialize_calendar_service()
    
    def clear_sheet_cache(self, spreadsheet_name: Optional[str] = None):
        """
        Clear cached sheets. If spreadsheet_name is provided, only clear
        cache for that specific spreadsheet. Otherwise, clear all cached sheets.
        
        Args:
            spreadsheet_name (Optional[str]): Name of spreadsheet to clear from cache,
                or None to clear all
        """
        if spreadsheet_name:
            # Clear all cache entries related to this spreadsheet
            keys_to_remove = [
                key for key in self._cached_sheets.keys()
                if key.startswith(f"{spreadsheet_name}:")
            ]
            for key in keys_to_remove:
                del self._cached_sheets[key]
        else:
            self._cached_sheets.clear()


# Create singleton instance
google_api_service = GoogleAPIService()
