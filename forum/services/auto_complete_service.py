"""
Service for handling auto-completion of courses from WolfNet
"""
import logging
from django.http import JsonResponse
from forum.tasks import auto_complete_courses
from django.conf import settings

logger = logging.getLogger(__name__)


def _execute_task_with_result(task_func, *args, **kwargs):
    """
    Execute a Celery task either synchronously or asynchronously based on result backend configuration.
    """
    result_backend_disabled = getattr(settings, 'CELERY_RESULT_BACKEND', None) is None
    
    if result_backend_disabled:
        # Run task synchronously when result backend is disabled
        return task_func(*args, **kwargs)
    else:
        # Run asynchronously with result retrieval
        task = task_func.delay(*args, **kwargs)
        return task.get(timeout=60)


def auto_complete_user_courses_service(user, wolfnet_password=None):
    """
    Auto-complete courses for a logged-in user from their WolfNet schedule
    
    This function retrieves a user's course schedule from WolfNet and attempts to match
    the courses with those in the local database. It uses either a provided password
    or the user's stored WolfNet password. Returns data in BlockSerializer format.
    
    Args:
        user (User): Django User instance - the authenticated user whose courses to fetch
        wolfnet_password (str, optional): WolfNet password to use for authentication.
                                        If not provided, will use the password stored
                                        in the user's profile. Defaults to None.

    Returns:
        dict: Response containing success status and user_data in BlockSerializer format
    """
    try:
        # Use provided password or get from user profile
        if wolfnet_password:
            password = wolfnet_password
        else:
            if not hasattr(user, 'userprofile') or not user.userprofile.wolfnet_password:
                return {
                    'success': False, 
                    'error': 'WolfNet password not configured. Please set up your WolfNet credentials in preferences.'
                }
            password = None  # Let the task retrieve it from the profile
        
        # Get user's school email
        school_email = user.school_email
        if not school_email:
            return {
                'success': False,
                'error': 'School email not found for user.'
            }
        
        # Start the auto-complete task
        if password:
            result = _execute_task_with_result(auto_complete_courses, school_email, password)
        else:
            result = _execute_task_with_result(auto_complete_courses, school_email)
        
        logger.info(f"Auto-complete courses result for {user.username}: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in auto_complete_user_courses for {user.username}: {str(e)}")
        return {
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }


def auto_complete_courses_registration_service(school_email, wolfnet_password):
    """
    Auto-complete courses during the user registration process from WolfNet
    
    This function is specifically designed for use during user registration when
    the user provides their WolfNet credentials to automatically populate their
    course schedule. It retrieves the course schedule from WolfNet and matches
    courses with the local database. Returns data in BlockSerializer format.
    
    Args:
        school_email (str): The user's school email address (e.g., 'student@school.edu').
                           This is used as the username for WolfNet authentication.
                           Must be a valid, non-empty string.
        wolfnet_password (str): The user's WolfNet password for authentication.
                              This is required and must be a valid, non-empty string.
                              The password is used only for this operation and is not
                              stored permanently during registration.
                              
    Returns:
        dict: Response containing success status and user_data in BlockSerializer format
    """
    try:
        if not wolfnet_password:
            return {
                'success': False, 
                'error': 'WolfNet password required for auto-completion.'
        }
            
        if not school_email:
            return {
                'success': False, 
                'error': 'School email required for auto-completion.'
            }
        
        # Start the auto-complete task
        result = _execute_task_with_result(auto_complete_courses, school_email, wolfnet_password)
        
        logger.info(f"Auto-complete courses result for registration {school_email}: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in auto_complete_courses_registration for {school_email}: {str(e)}")
        return {
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }
