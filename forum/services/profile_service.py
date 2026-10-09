import json
import os
from PIL import Image
from io import BytesIO
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import Coalesce
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from forum.models import Course, Post, Solution, User, UserCourseExperience, UserCourseHelp, UserProfile
from forum.services.utils import detect_bad_words
from forum.services.post_list_service import prepare_posts
from forum.serializers.user import USER_SCHEDULE_BLOCKS
from forum.services.schedule_import_service import ScheduleImportValidationError, replace_user_schedule
from forum.services.results import service_error, service_success

PROFILE_FIELDS = (
    'first_name', 'last_name', 'personal_email', 'phone_number', 'bio',
    'instagram_handle', 'snapchat_handle', 'linkedin_url',
    'preferred_msg_app', 'background_hue',
)


def get_profile_user(username):
    return User.objects.filter(username=username).select_related('userprofile').first()


def compress_image(image_file, max_width=1200, quality=85):
    """
    Compress an image file to reduce storage size.
    
    Args:
        image_file: Django UploadedFile object
        max_width: Maximum width in pixels (default 1200)
        quality: JPEG quality 1-100 (default 85, good balance)
    
    Returns:
        ContentFile: Compressed image file ready to save
    """
    img = Image.open(image_file)
    
    # Convert RGBA to RGB for JPEG compression
    if img.mode in ('RGBA', 'LA', 'P'):
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = rgb_img
    
    # Resize if larger than max_width
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    
    # Compress and save to BytesIO
    output = BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    output.seek(0)
    
    return ContentFile(output.getvalue())


def get_profile_posts_page(viewing_user, profile_user, page=1, per_page=8):
    """Return paginated public profile posts for a target user."""
    page = int(page)
    per_page = int(per_page)

    base_qs = Post.objects.filter(
        author=profile_user,
        is_anonymous=False,
    )

    if viewing_user.is_authenticated and viewing_user.is_teacher:
        base_qs = base_qs.filter(allow_teacher=True)

    base_qs = base_qs.annotate(
        recent_updated_at=Coalesce('last_activity_at', 'created_at')
    ).order_by('-recent_updated_at', '-created_at')

    paginator = Paginator(base_qs, per_page)

    # Return an empty page if page number is out of range.
    if page > paginator.num_pages and paginator.num_pages > 0:
        empty_page = paginator.get_page(paginator.num_pages)
        empty_page.object_list = []
        return empty_page

    page_obj = paginator.get_page(page)
    post_ids = [post.id for post in page_obj.object_list]

    posts_qs = Post.objects.filter(id__in=post_ids).annotate(
        solution_count=Count('solutions', distinct=True),
        comment_count=Count('solutions__comments', distinct=True),
        total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True)
    ).select_related('author').prefetch_related('courses', 'solutions__comments')

    posts_dict = {post.id: post for post in posts_qs}
    ordered_posts = [posts_dict[pid] for pid in post_ids if pid in posts_dict]
    ordered_posts = prepare_posts(ordered_posts, viewing_user)

    page_obj.object_list = ordered_posts
    return page_obj

def get_profile_context(viewing_user, profile_user, profile_data):
    """Build profile-page data from already resolved application objects."""
    recent_posts_page = get_profile_posts_page(viewing_user, profile_user, page=1, per_page=3)
    recent_posts = recent_posts_page.object_list
    posts_count = Post.objects.filter(author=profile_user).count()
    solutions_count = Solution.objects.filter(author=profile_user).count()

    initial_courses_json = json.dumps(profile_data['schedule'] or {})

    experienced_courses = UserCourseExperience.objects.filter(user=profile_user)
    help_needed_courses = UserCourseHelp.objects.filter(user=profile_user, active=True)
    experienced_courses_json = json.dumps([experience.course.id for experience in experienced_courses])
    help_needed_courses_json = json.dumps([help.course.id for help in help_needed_courses])

    all_courses = Course.objects.all().order_by('category', 'name')

    context = {
        'profile_user': profile_user,
        'profile_data': profile_data,
        'recent_posts': recent_posts,
        'posts_count': posts_count,
        'solutions_count': solutions_count,
        'experienced_courses': experienced_courses,
        'help_needed_courses': help_needed_courses,
        'experienced_courses_json': experienced_courses_json,
        'help_needed_courses_json': help_needed_courses_json,
        'initial_courses_json': initial_courses_json,
        'all_courses': all_courses
    }

    from forum.services.community_services import is_following_community
    context['is_following_community'] = is_following_community(viewing_user, profile_user)
    if viewing_user == profile_user and profile_user.is_community_account and profile_user.is_active:
        from forum.services.community_services import get_owned_community_lunches
        context['community_lunches'] = get_owned_community_lunches(profile_user)['lunches']
    
    context['can_compare'] = profile_data['can_compare']
    context['initial_users'] = json.dumps(profile_data['initial_users'])

    return context

def update_profile_info(user, profile_user, data):
    """Update a user's profile from plain values supplied by an entry point."""
    if user != profile_user:
        return service_error('You can only update your own profile.', 403)

    data = dict(data)
    for field in PROFILE_FIELDS:
        if field == 'background_hue':
            continue
        if field not in data:
            continue
        if data[field] is None and field not in ('first_name', 'last_name'):
            data[field] = ''
        if not isinstance(data[field], str):
            return service_error(f'Invalid {field.replace("_", " ")}.')

    if 'background_hue' in data:
        try:
            if isinstance(data['background_hue'], bool):
                raise ValueError
            data['background_hue'] = int(data['background_hue'])
        except (TypeError, ValueError):
            return service_error('Background hue must be a number from 0 to 360.')
        if not 0 <= data['background_hue'] <= 360:
            return service_error('Background hue must be a number from 0 to 360.')
    try:
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.personal_email = data.get('personal_email', user.personal_email)
        user.phone_number = data.get('phone_number', user.phone_number)

        if 'bio' in data:
            bio = data.get('bio', profile_user.userprofile.bio)
            detect_bad_words(bio)
            profile_user.userprofile.bio = bio

        # Handle social media links
        if 'instagram_handle' in data:
            instagram_handle = data.get('instagram_handle', '').strip().lstrip('@')
            profile_user.userprofile.instagram_handle = instagram_handle if instagram_handle else None
        
        if 'snapchat_handle' in data:
            snapchat_handle = data.get('snapchat_handle', '').strip().lstrip('@')
            profile_user.userprofile.snapchat_handle = snapchat_handle if snapchat_handle else None
        
        if 'linkedin_url' in data:
            linkedin_url = data.get('linkedin_url', '').strip()
            # Validate LinkedIn URL
            if linkedin_url:
                if not (linkedin_url.startswith('https://www.linkedin.com/in/') or 
                        linkedin_url.startswith('http://www.linkedin.com/in/') or
                        linkedin_url.startswith('www.linkedin.com/in/')):
                    return service_error('LinkedIn URL must start with www.linkedin.com/in/')
                
                # Ensure https protocol
                if linkedin_url.startswith('www.'):
                    linkedin_url = 'https://' + linkedin_url
                elif linkedin_url.startswith('http://'):
                    linkedin_url = linkedin_url.replace('http://', 'https://')
            profile_user.userprofile.linkedin_url = linkedin_url if linkedin_url else None

        if 'preferred_msg_app' in data:
            preferred_msg_app = data.get('preferred_msg_app')
            if preferred_msg_app is None:
                preferred_msg_app = ''
            elif not isinstance(preferred_msg_app, str):
                return service_error('Invalid preferred messaging app.')
            preferred_msg_app = preferred_msg_app.strip()
            if preferred_msg_app and preferred_msg_app not in UserProfile.PreferredMessageApp.values:
                return service_error('Invalid preferred messaging app.')
            profile_user.userprofile.preferred_msg_app = preferred_msg_app or None

        profile_user.userprofile.background_hue = data.get(
            'background_hue', profile_user.userprofile.background_hue
        )
        user.save()
        profile_user.userprofile.save()

        return service_success('Profile updated successfully!')
    except ValueError as e:
        return service_error(e)
    except Exception as e:
        return service_error(f'Error updating profile: {e}', 500)

def update_privacy_preferences(profile_user, allow_schedule_comparison, display_email=None):
    """Handle privacy preferences update"""
    try:
        profile_user.userprofile.allow_schedule_comparison = allow_schedule_comparison
        update_fields = ['allow_schedule_comparison']
        if display_email is not None:
            profile_user.userprofile.display_email = display_email
            update_fields.append('display_email')
        profile_user.userprofile.save(update_fields=update_fields)
        
        return service_success('Privacy preferences updated successfully!')
    except Exception as e:
        return service_error(f'Error updating privacy preferences: {e}', 500)

def update_profile_picture(user, image_file):
    """
    Update user profile picture with compression.
    
    - Validates file type and input size (max 5 MB)
    - Compresses to JPEG format (except for GIFs, which are kept original)
    - Resizes to max 1200px width
    - Stores in profile_pictures/ directory
    - Deletes old picture if not default
    
    Returns:
        tuple: (success: bool, message: str)
    """
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/heic', 'image/webp']
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp']
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB (input file size before compression)
    
    if image_file is None:
        return service_error('No profile picture file provided')
    ext = os.path.splitext(image_file.name)[1].lower()
    mime_type = image_file.content_type
    
    # Validate file size before compression
    if image_file.size > MAX_IMAGE_SIZE:
        return service_error(f'Image file too large. Maximum size is 5 MB, got {image_file.size / (1024*1024):.1f} MB')
    
    # Validate file type
    if mime_type not in ALLOWED_IMAGE_TYPES or ext not in ALLOWED_EXTENSIONS:
        return service_error(f'Unsupported file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}')
    
    try:
        import uuid
        profile = user.userprofile
        
        # GIFs are kept as-is to preserve animation
        if mime_type == 'image/gif':
            unique_name = f"{uuid.uuid4().hex}.gif"
            upload_path = os.path.join('profile_pictures', unique_name)
            
            # Save original GIF without compression
            saved_path = default_storage.save(upload_path, image_file)
        else:
            # Compress other formats to JPEG for consistency and efficiency
            compressed_file = compress_image(image_file, max_width=1200, quality=85)
            
            # Generate unique filename, save as JPG
            unique_name = f"{uuid.uuid4().hex}.jpg"
            upload_path = os.path.join('profile_pictures', unique_name)
            saved_path = default_storage.save(upload_path, compressed_file)
        
        # Delete old picture if not default
        if profile.profile_picture and profile.profile_picture.name != 'profile_pictures/default.png':
            try:
                profile.profile_picture.delete(save=False)
            except Exception as e:
                print(f"Warning: Could not delete previous profile picture: {str(e)}")
        
        # Save updated profile
        profile.profile_picture = saved_path
        profile.save()
        
        return service_success('Profile picture updated successfully')
        
    except Exception as e:
        return service_error(f'Error processing image: {e}', 500)

def update_lunch_card(user, image_file):
    """
    Update user lunch card without compression (original quality).
    
    - Validates file type and size (max 5 MB)
    - Stores original image without compression
    - Stores in lunch_cards/ directory
    - Deletes old lunch card if it exists
    
    Returns:
        tuple: (success: bool, message: str)
    """
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/heic', 'image/webp']
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp']
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB (no compression)
    
    if image_file is None:
        return service_error('No lunch card file provided')
    ext = os.path.splitext(image_file.name)[1].lower()
    mime_type = image_file.content_type
    
    # Validate file size
    if image_file.size > MAX_IMAGE_SIZE:
        return service_error(f'Image file too large. Maximum size is 5 MB, got {image_file.size / (1024*1024):.1f} MB')
    
    # Validate file type
    if mime_type not in ALLOWED_IMAGE_TYPES or ext not in ALLOWED_EXTENSIONS:
        return service_error(f'Unsupported file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}')
    
    try:
        # Keep original file without compression
        image_file_to_save = image_file
        
        # Generate unique filename, keep original extension
        import uuid
        original_ext = os.path.splitext(image_file.name)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{original_ext}"
        upload_path = os.path.join('lunch_cards', unique_name)
        
        profile = user.userprofile
        
        # Delete old lunch card if it exists
        if profile.lunch_card:
            try:
                profile.lunch_card.delete(save=False)
            except Exception as e:
                print(f"Warning: Could not delete previous lunch card: {str(e)}")
        
        # Save original file without compression
        saved_path = default_storage.save(upload_path, image_file_to_save)
        profile.lunch_card = saved_path
        profile.save()
        
        return service_success('Lunch card updated successfully')
        
    except Exception as e:
        return service_error(f'Error processing image: {e}', 500)

def delete_lunch_card(user):
    """Delete a user's stored lunch card."""
    profile = user.userprofile
    if not profile.lunch_card:
        return service_error('No lunch card to delete')
    try:
        profile.lunch_card.delete(save=True)
        return service_success('Lunch card deleted successfully!')
    except Exception as e:
        return service_error(f'Error deleting lunch card: {e}', 500)


def update_profile_courses(user, data):
    profile = user.userprofile
    try:
        assignments = {}
        for block in USER_SCHEDULE_BLOCKS:
            key = f'block_{block}'
            if key in data:
                value = data.get(key)
                assignments[block] = None if value in (None, '', 'NOCOURSE') else value
            else:
                assignments[block] = getattr(profile, f'{key}_id', None)

        replace_user_schedule(profile, assignments, allow_empty=True)
        return service_success('Courses updated successfully!')
    except ScheduleImportValidationError as exc:
        return service_error(exc)
    except Exception as e:
        return service_error(f"Error updating courses: {e}", 500)

def add_user_experience(user, course_id):
    try:
        if not course_id:
            return service_error('Course ID is required.')
        
        # Check if course exists
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return service_error('Course not found.', 404)
        
        # Check if experience already exists
        if UserCourseExperience.objects.filter(user=user, course=course).exists():
            return service_error('You already have experience with this course.', 409)
        
        # Create the experience
        experience = UserCourseExperience.objects.create(
            user=user,
            course=course
        )
        return service_success(
            'Course experience added successfully!',
            id=experience.id,
            course_id=course.id,
            course_name=course.name,
        )
        
    except Exception as e:
        return service_error(f'Error adding course experience: {e}', 500)

def add_user_help_request(user, course_id):
    try:
        if not course_id:
            return service_error('Course ID is required.')
        
        # Check if course exists
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return service_error('Course not found.', 404)
        
        # Check if help request already exists
        if UserCourseHelp.objects.filter(user=user, course=course, active=True).exists():
            return service_error('You already have an active help request for this course.', 409)
        
        # Create the help request
        help_request = UserCourseHelp.objects.create(
            user=user,
            course=course,
            active=True
        )
        return service_success(
            'Help request added successfully!',
            id=help_request.id,
            course_id=course.id,
            course_name=course.name,
        )
        
    except Exception as e:
        return service_error(f'Error adding help request: {e}', 500)

def remove_user_experience(user, experience_id):
    try:
        experience = UserCourseExperience.objects.filter(id=experience_id, user=user).first()
        if experience is None:
            return service_error('Course experience not found.', 404)
        course_id = experience.course_id
        experience.delete()
        return service_success('Course experience removed successfully!', course_id=course_id)
    except Exception as e:
        return service_error(f'Error removing course experience: {e}', 500)

def remove_user_help_request(user, help_id):
    try:
        help_request = UserCourseHelp.objects.filter(id=help_id, user=user).first()
        if help_request is None:
            return service_error('Help request not found.', 404)
        course_id = help_request.course_id
        help_request.delete()
        return service_success('Help request removed successfully!', course_id=course_id)
    except Exception as e:
        return service_error(f'Error removing help request: {e}', 500)
