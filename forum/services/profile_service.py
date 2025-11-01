import json
from django.shortcuts import get_object_or_404
from forum.models import User, Course, Post, Solution, UserCourseExperience, UserCourseHelp, UserProfile
from forum.forms import UserCourseExperienceForm, UserCourseHelpForm
from forum.services.utils import detect_bad_words
from forum.serializers import BlockSerializer

def get_profile_context(request, username):
    profile_user = get_object_or_404(User, username=username)
    recent_posts = Post.objects.filter(
        author=profile_user,
        is_anonymous=False
    ).order_by('-created_at')[:3]
    posts_count = Post.objects.filter(author=profile_user).count()
    solutions_count = Solution.objects.filter(author=profile_user).count()

    # Use the BlockSerializer as the canonical source for schedule data
    serializer = BlockSerializer(profile_user.userprofile)
    initial_courses = serializer.data.get('schedule', {}) if serializer and serializer.data else {}
    
    initial_courses_json = json.dumps(initial_courses)

    experienced_courses = UserCourseExperience.objects.filter(user=profile_user)
    help_needed_courses = UserCourseHelp.objects.filter(user=profile_user, active=True)
    experienced_courses_json = json.dumps([experience.course.id for experience in experienced_courses])
    help_needed_courses_json = json.dumps([help.course.id for help in help_needed_courses])

    all_courses = Course.objects.all().order_by('category', 'name')

    context = {
        'profile_user': profile_user,
        'recent_posts': recent_posts,
        'posts_count': posts_count,
        'solutions_count': solutions_count,
        'experienced_courses': experienced_courses,
        'help_needed_courses': help_needed_courses,
        'experienced_courses_json': experienced_courses_json,
        'help_needed_courses_json': help_needed_courses_json,
        'initial_courses_json': initial_courses_json,
        'has_wolfnet_password' : bool(profile_user.userprofile.wolfnet_password),
        'all_courses': all_courses
    }
    
    # Add comparison data if viewing someone else's profile
    if request.user.is_authenticated and request.user != profile_user:
        initial_users = [
            {
                'id': request.user.id,
                'username': request.user.username,
                'full_name': request.user.get_full_name(),
                'school_email': request.user.school_email,
                'profile_picture_url': request.user.userprofile.profile_picture.url if request.user.userprofile.profile_picture else None,
            },
            {
                'id': profile_user.id,
                'username': profile_user.username,
                'full_name': profile_user.get_full_name(),
                'school_email': profile_user.school_email,
                'profile_picture_url': profile_user.userprofile.profile_picture.url if profile_user.userprofile.profile_picture else None,
            }
        ]
        context['initial_users'] = json.dumps(initial_users)
        context['can_compare'] = True
    else:
        context['can_compare'] = False
    
    return context

def update_profile_info(request, username):
    profile_user = get_object_or_404(User, username=username)
    try:
        # Handle WolfNet settings form
        if request.POST.get('form_type') == 'wolfnet_settings':
            return update_wolfnet_settings(request, profile_user)
        
        # Handle privacy preferences form
        if request.POST.get('form_type') == 'privacy_preferences':
            return update_privacy_preferences(request, profile_user)
        
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.personal_email = request.POST.get('personal_email', request.user.personal_email)
        request.user.phone_number = request.POST.get('phone_number', request.user.phone_number)
        request.user.save()

        if 'bio' in request.POST:
            bio = request.POST.get('bio', profile_user.userprofile.bio)
            detect_bad_words(bio)
            profile_user.userprofile.bio = bio
            profile_user.userprofile.save()

        hue_value = request.POST.get('background_hue', profile_user.userprofile.background_hue)
        profile_user.userprofile.background_hue = int(hue_value)
        profile_user.userprofile.save()

        return True, 'Profile updated successfully!'
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f'Error updating profile: {str(e)}'

def update_privacy_preferences(request, profile_user):
    """Handle privacy preferences update"""
    try:
        allow_schedule_comparison = request.POST.get('allow_schedule_comparison') == 'on'
        allow_grade_updates = request.POST.get('allow_grade_updates') == 'on'
        
        profile_user.userprofile.allow_schedule_comparison = allow_schedule_comparison
        profile_user.userprofile.allow_grade_updates = allow_grade_updates
        profile_user.userprofile.save()
        
        return True, 'Privacy preferences updated successfully!'
    except Exception as e:
        return False, f'Error updating privacy preferences: {str(e)}'

def update_wolfnet_settings(request, profile_user):
    """Handle WolfNet settings update"""
    try:
        # Check if we're clearing the password
        if request.POST.get('clear_wolfnet_password') == 'true':
            profile_user.userprofile.wolfnet_password = None
            profile_user.userprofile.save()
            return True, 'WolfNet password cleared successfully!'
        
        # Otherwise, update the password
        wolfnet_password = request.POST.get('wolfnet_password', '').strip()
        if wolfnet_password:
            from forum.forms import WolfNetSettingsForm
            encrypted_password = WolfNetSettingsForm().encrypt_password(wolfnet_password)
            profile_user.userprofile.wolfnet_password = encrypted_password
            profile_user.userprofile.save()
            return True, 'WolfNet settings updated successfully! Grade notifications and schedule integration are now enabled.'
        else:
            return False, 'Please enter a valid WolfNet password.'
            
    except Exception as e:
        return False, f'Error updating WolfNet settings: {str(e)}'

def update_profile_picture(request):
    profile = request.user.userprofile
    
    # Only delete the old picture if it's not the default one
    if profile.profile_picture and profile.profile_picture.name != 'profile_pictures/default.png':
        try:
            profile.profile_picture.delete(save=False)
        except Exception as e:
            print(f"Warning: Could not delete previous profile picture: {str(e)}")
    
    profile.profile_picture = request.FILES['profile_picture']
    profile.save()

def update_profile_courses(request):
    profile = request.user.userprofile
    try:
        for key, value in request.POST.items():
            if key.startswith("block_"):
                block = key.replace("block_", "")
                course_id = value
                if course_id == 'NOCOURSE':
                    setattr(profile, f'block_{block}', None)
                else:
                    course = Course.objects.get(id=course_id)
                    setattr(profile, f'block_{block}', course)
        profile.save()
        return True, 'Courses updated successfully!'
    except Course.DoesNotExist:
        return False, f"Course with ID {course_id} does not exist."
    except Exception as e:
        return False, f"Error updating courses: {str(e)}"

def add_user_experience(request):
    try:
        course_id = request.POST.get('course')
        if not course_id:
            return False, 'Course ID is required.'
        
        # Check if course exists
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return False, 'Course not found.'
        
        # Check if experience already exists
        if UserCourseExperience.objects.filter(user=request.user, course=course).exists():
            return False, 'You already have experience with this course.'
        
        # Create the experience
        UserCourseExperience.objects.create(
            user=request.user,
            course=course
        )
        return True, None
        
    except Exception as e:
        return False, f'Error adding course experience: {str(e)}'

def add_user_help_request(request):
    try:
        course_id = request.POST.get('course')
        if not course_id:
            return False, 'Course ID is required.'
        
        # Check if course exists
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return False, 'Course not found.'
        
        # Check if help request already exists
        if UserCourseHelp.objects.filter(user=request.user, course=course, active=True).exists():
            return False, 'You already have an active help request for this course.'
        
        # Create the help request
        UserCourseHelp.objects.create(
            user=request.user,
            course=course,
            active=True
        )
        return True, None
        
    except Exception as e:
        return False, f'Error adding help request: {str(e)}'

def remove_user_experience(request, experience_id):
    try:
        experience = get_object_or_404(UserCourseExperience, id=experience_id, user=request.user)
        experience.delete()
        return True, 'Course experience removed successfully!'
    except UserCourseExperience.DoesNotExist:
        return False, 'Course experience not found.'
    except Exception as e:
        return False, f'Error removing course experience: {str(e)}'

def remove_user_help_request(request, help_id):
    try:
        help_request = get_object_or_404(UserCourseHelp, id=help_id, user=request.user)
        help_request.delete()
        return True, 'Help request removed successfully!'
    except UserCourseHelp.DoesNotExist:
        return False, 'Help request not found.'
    except Exception as e:
        return False, f'Error removing help request: {str(e)}'
