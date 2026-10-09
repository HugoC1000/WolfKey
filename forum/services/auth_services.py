from forum.models import User, UserCourseHelp, UserCourseExperience
from forum.services.utils import generate_username
from forum.services.results import service_error, service_success

def authenticate_user(school_email, password):
    try:
        user = User.objects.get(school_email=school_email)
    except User.DoesNotExist:
        return service_error("No account found with this school email", 401)

    if not user.is_active:
        return service_error("This account is inactive. Contact WolfKey support.", 401)

    if not user.check_password(password):
        return service_error("Invalid password", 401)

    return service_success(user=user)

def register_user(user_data, help_courses, experience_courses, schedule_data=None, allow_schedule_comparison=True):
    """
    Centralized service for user registration
    Returns a user on success or an error with a status on failure.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Lower the threshold for registration - these are optional now
        if len(experience_courses) > 0 and len(experience_courses) < 2:
            logger.warning("Experience courses validation failed: less than 2 selected")
            return service_error('If selecting experience courses, please select at least 2.')
            
        if len(help_courses) > 0 and len(help_courses) < 2:
            logger.warning("Help courses validation failed: less than 2 selected")
            return service_error('If selecting help courses, please select at least 2.')

        user = User(
            username=generate_username(user_data['first_name'], user_data['last_name']),
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            school_email=user_data['school_email'],
            personal_email=user_data.get('personal_email') or user_data['school_email'],
            is_teacher=user_data['user_type'] == 'teacher',
        )
        user.set_password(user_data['password1'])
        user.save()

        grade_level = user_data.get('grade_level')
        if grade_level not in (None, ''):
            user.userprofile.grade_level = int(grade_level)
        logger.info(f"User object created: {user.school_email}")
        
        # Set user preferences
        user.userprofile.allow_schedule_comparison = allow_schedule_comparison
        
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
                logger.info(f"Schedule data saved for {len(schedule_data)} blocks")
            except Exception as e:
                logger.error(f"Failed to save schedule data: {str(e)}")

        user.userprofile.save()
        
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
        
        return service_success(user=user)
        
    except Exception as e:
        logger.error(f"Registration failed with exception: {str(e)}", exc_info=True)
        return service_error(e, 500)
