import json
import os
from django.core.management.base import BaseCommand
from forum.services.schedule_services import rebuild_date_row_cache

class Command(BaseCommand):
    help = 'Rebuild the schedule date-to-row number cache from the Google Sheet'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting schedule cache rebuild...'))
        
        try:
            count = rebuild_date_row_cache()
            self.stdout.write(
                self.style.SUCCESS(f'✓ Successfully cached {count} dates from the schedule sheet')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error rebuilding cache: {str(e)}')
            )
            raise
