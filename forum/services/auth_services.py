from django.contrib.auth import login
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from forum.models import User, UserCourseHelp, UserCourseExperience

def authenticate_user(request, school_email, password):
    try:
        user = User.objects.get(school_email=school_email)
    except User.DoesNotExist:
        return None, "No account found with this school email"

    if not user.check_password(password):
        return None, "Invalid password"

    return user, None

@ensure_csrf_cookie
def get_csrf_token(request):
    return JsonResponse({'csrfToken': request.META.get('CSRF_COOKIE')})


def register_user(request, form, help_courses, experience_courses, wolfnet_password=None, schedule_data=None, allow_schedule_comparison=True, allow_grade_updates=True):
    """
    Centralized service for user registration
    Returns (user, error_message) tuple
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Lower the threshold for registration - these are optional now
        if len(experience_courses) > 0 and len(experience_courses) < 2:
            logger.warning("Experience courses validation failed: less than 2 selected")
            return None, 'If selecting experience courses, please select at least 2.'
            
        if len(help_courses) > 0 and len(help_courses) < 2:
            logger.warning("Help courses validation failed: less than 2 selected")
            return None, 'If selecting help courses, please select at least 2.'

        user = form.save()
        logger.info(f"User object created: {user.school_email}")
        
        # Set user preferences
        user.userprofile.allow_schedule_comparison = allow_schedule_comparison
        user.userprofile.allow_grade_updates = allow_grade_updates
        
        # Set WolfNet password if provided
        if wolfnet_password:
            try:
                from forum.forms import WolfNetSettingsForm
                wolfnet_form = WolfNetSettingsForm()
                encrypted_password = wolfnet_form.encrypt_password(wolfnet_password)
                user.userprofile.wolfnet_password = encrypted_password
                user.userprofile.save()
                logger.info("WolfNet password encrypted and saved")
            except Exception as e:
                logger.error(f"Failed to encrypt WolfNet password: {str(e)}")
                # Don't fail registration if WolfNet password encryption fails
                pass
        
        # Set schedule courses if provided
        if schedule_data:
            try:
                from forum.models import Course
                for block_key, course_id in schedule_data.items():
                    if isinstance(course_id, int):
                        try:
                            course = Course.objects.get(id=course_id)
                            setattr(user.userprofile, block_key, course)
                        except Course.DoesNotExist:
                            logger.warning(f"Course {course_id} not found for block {block_key}")
                            pass
                user.userprofile.save()
                logger.info(f"Schedule data saved for {len(schedule_data)} blocks")
            except Exception as e:
                logger.error(f"Failed to save schedule data: {str(e)}")
        
        # Add help courses
        for course_id in help_courses:
            if isinstance(course_id, int):
                try:
                    UserCourseHelp.objects.create(
                        user=user,
                        course_id=course_id,
                        active=True
                    )
                except Exception as e:
                    logger.error(f"Failed to add help course {course_id}: {str(e)}")
            
        # Add experience courses
        for course_id in experience_courses:
            if isinstance(course_id, int):
                try:
                    UserCourseExperience.objects.create(
                        user=user,
                        course_id=course_id
                    )
                except Exception as e:
                    logger.error(f"Failed to add experience course {course_id}: {str(e)}")
        
        login(request, user)
        logger.info(f"User {user.school_email} logged in successfully")
        return user, None
        
    except Exception as e:
        logger.error(f"Registration failed with exception: {str(e)}", exc_info=True)
        return None, str(e)