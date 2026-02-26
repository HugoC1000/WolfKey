from django.core.management.base import BaseCommand
from forum.services import volunteer_service
import gspread


class Command(BaseCommand):
    help = 'Check WPGA service hours for students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--student-number',
            type=str,
            help='Get service hours for a specific student number'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Get all service hours'
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Interactive mode - enter student numbers one by one'
        )
        parser.add_argument(
            '--refresh',
            action='store_true',
            help='Force refresh the cache before querying'
        )

    def handle(self, *args, **options):
        # Handle --refresh flag
        if options.get('refresh'):
            self.stdout.write('Clearing cache and forcing refresh...')
            volunteer_service.clear_cache()
        
        # Handle --all flag
        if options.get('all'):
            self.stdout.write('Fetching all service hours...')
            try:
                all_hours = volunteer_service.get_all_service_hours()
                if all_hours:
                    self.stdout.write(self.style.SUCCESS(f'\nFound {len(all_hours)} students:'))
                    for student_number, hours in sorted(all_hours.items()):
                        self.stdout.write(f'  Student {student_number}: {hours} hours')
                else:
                    self.stdout.write(self.style.WARNING('No service hours found'))
            except gspread.SpreadsheetNotFound:
                self.stdout.write(self.style.ERROR('Error: Spreadsheet "WPGA Service Hour Tracking" not found'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            return
        
        # Handle --interactive flag
        if options.get('interactive'):
            self.stdout.write(self.style.SUCCESS('Interactive mode - Enter student numbers (or "quit" to exit)'))
            while True:
                try:
                    student_number = input('\nEnter student number: ').strip()
                    if student_number.lower() in ['quit', 'exit', 'q']:
                        self.stdout.write(self.style.SUCCESS('\nGoodbye!'))
                        break
                    
                    if not student_number:
                        self.stdout.write(self.style.WARNING('Please enter a valid student number'))
                        continue
                    
                    self._check_student(student_number)
                    
                except KeyboardInterrupt:
                    self.stdout.write(self.style.SUCCESS('\n\nGoodbye!'))
                    break
                except EOFError:
                    self.stdout.write(self.style.SUCCESS('\n\nGoodbye!'))
                    break
            return
        
        # Handle --student-number flag
        student_number = options.get('student_number')
        if student_number:
            self._check_student(student_number)
        else:
            # No flags provided - show help
            self.stdout.write(self.style.WARNING('Please provide either:'))
            self.stdout.write('  --student-number <number>  : Check a specific student')
            self.stdout.write('  --all                      : Get all service hours')
            self.stdout.write('  --interactive              : Interactive mode')
            self.stdout.write('  --refresh                  : Force cache refresh')
            self.stdout.write('\nExample: python manage.py check_service_hours --interactive')
    
    def _check_student(self, student_number):
        """Helper method to check a single student's hours."""
        try:
            hours = volunteer_service.get_volunteer_hours(student_number)
            
            if hours is None:
                self.stdout.write(
                    self.style.WARNING(f'Student {student_number} not found in the spreadsheet')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Student {student_number} has {hours} volunteer hours')
                )
        except gspread.SpreadsheetNotFound:
            self.stdout.write(
                self.style.ERROR('Error: Spreadsheet "WPGA Service Hour Tracking" not found')
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
