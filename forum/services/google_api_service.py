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
            self._calendar_service = build('calendar', 'v3', credentials=creds)
        return self._calendar_service
    
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
            spreadsheet = client.open(spreadsheet_name)
            self._cached_sheets[cache_key] = spreadsheet.get_worksheet(worksheet_index)
        
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
            spreadsheet = client.open_by_key(spreadsheet_key)
            self._cached_sheets[cache_key] = spreadsheet.get_worksheet(worksheet_index)
        
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
