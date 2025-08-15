"""
API endpoints for profile management
"""
import json
import logging
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from forum.models import User, UserCourseExperience, UserCourseHelp
from forum.services.profile_service import (
    get_profile_context,
    update_profile_info,
    update_profile_picture,
    update_profile_courses,
    add_user_experience,
    add_user_help_request,
    remove_user_experience,
    remove_user_help_request,
)

logger = logging.getLogger(__name__)

User = get_user_model()


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_profile_api(request, username=None):
    """
    Get profile information for a user
    
    Args:
        username (str, optional): Username of the profile to get. If not provided, returns current user's profile
    
    Returns:
        Response: Profile data including user info, courses, posts count, etc.
    """
    try:
        if not username:
            username = request.user.username
            
        profile_user = get_object_or_404(User, username=username)
        
        if not hasattr(profile_user, 'userprofile'):
            from forum.models import UserProfile
            UserProfile.objects.create(user=profile_user)
        
        context = get_profile_context(request, username)
        
        blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        schedule_blocks = {}
        for block in blocks:
            course = getattr(profile_user.userprofile, f'block_{block}', None)
            if course:
                schedule_blocks[f'block_{block}'] = {
                    'id': course.id,
                    'name': course.name,
                    'category': course.category,
                }
            else:
                schedule_blocks[f'block_{block}'] = None

        profile_data = {
            'user': {
                'id': profile_user.id,
                'username': profile_user.username,
                'first_name': profile_user.first_name,
                'last_name': profile_user.last_name,
                'school_email': profile_user.school_email,
                'personal_email': getattr(profile_user, 'personal_email', ''),
                'phone_number': getattr(profile_user, 'phone_number', ''),
                'profile_picture_url': profile_user.userprofile.profile_picture.url if profile_user.userprofile.profile_picture else None,
                'bio': profile_user.userprofile.bio,
                'background_hue': profile_user.userprofile.background_hue,
                'has_wolfnet_password': context['has_wolfnet_password'],
                'schedule_blocks': schedule_blocks
            },
            'stats': {
                'posts_count': context['posts_count'],
                'solutions_count': context['solutions_count']
            },
            'courses': {
                'experienced_courses': [
                    {
                        'id': exp.id,
                        'course': {
                            'id': exp.course.id,
                            'name': exp.course.name,
                            'category': exp.course.category
                        }
                    } for exp in context['experienced_courses']
                ],
                'help_needed_courses': [
                    {
                        'id': help_req.id,
                        'course': {
                            'id': help_req.course.id,
                            'name': help_req.course.name,
                            'category': help_req.course.category
                        }
                    } for help_req in context['help_needed_courses']
                ],
                'schedule_courses': json.loads(context['initial_courses_json'])
            },
            'recent_posts': [
                {
                    'id': post.id,
                    'title': post.title,
                    'created_at': post.created_at.isoformat(),
                    'likes_count': post.like_count(),
                    'solutions_count': post.solutions.count()
                } for post in context['recent_posts']
            ],
            'can_compare': context['can_compare']
        }
        
        if context['can_compare']:
            profile_data['initial_users'] = json.loads(context['initial_users'])
            
        return Response(profile_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting profile for {username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_profile_api(request):
    """
    Update profile information for the current user
    
    Request body can contain:
        - first_name: User's first name
        - last_name: User's last name
        - personal_email: User's personal email
        - phone_number: User's phone number
        - bio: User's bio
        - background_hue: Background hue value (integer)
        - form_type: Type of form ('wolfnet_settings' for WolfNet settings)
        - wolfnet_password: WolfNet password (if form_type is 'wolfnet_settings')
        - clear_wolfnet_password: Boolean to clear WolfNet password
    
    Returns:
        Response: Success message or error
    """
    try:
        # Create a mock POST request for the service
        mock_request = type('MockRequest', (), {
            'POST': request.data,
            'user': request.user,
            'method': 'POST'
        })()
        
        success, msg = update_profile_info(mock_request, request.user.username)
        
        if success:
            return Response({'message': msg}, status=status.HTTP_200_OK)
        else:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error updating profile for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def upload_profile_picture_api(request):
    """
    Upload profile picture for the current user
    
    Request should contain a file in 'profile_picture' field
    
    Returns:
        Response: Success message and new profile picture URL or error
    """
    try:
        if 'profile_picture' not in request.FILES:
            return Response({
                'error': 'No profile picture file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a mock request for the service
        mock_request = type('MockRequest', (), {
            'FILES': request.FILES,
            'user': request.user
        })()
        
        update_profile_picture(mock_request)
        
        return Response({
            'message': 'Profile picture updated successfully!',
            'profile_picture_url': request.user.userprofile.profile_picture.url
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error uploading profile picture for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_courses_api(request):
    """
    Update schedule courses for the current user
    
    Request body should contain course assignments for blocks:
        - block_1A: Course ID or 'NOCOURSE'
        - block_1B: Course ID or 'NOCOURSE'
        - etc.
    
    Returns:
        Response: Success message or error
    """
    try:
        # Create a mock POST request for the service
        mock_request = type('MockRequest', (), {
            'POST': request.data,
            'user': request.user
        })()
        
        success, msg = update_profile_courses(mock_request)
        
        if success:
            return Response({'message': msg}, status=status.HTTP_200_OK)
        else:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error updating courses for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_experience_api(request):
    """
    Add course experience for the current user
    
    Request body should contain:
        - course: Course ID
    
    Returns:
        Response: Success message or error
    """
    try:
        # Create a mock POST request for the service
        mock_request = type('MockRequest', (), {
            'POST': request.data,
            'user': request.user
        })()
        
        success, error = add_user_experience(mock_request)
        
        if success:
            return Response({'message': 'Course experience added successfully!'}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error adding experience for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def add_help_request_api(request):
    """
    Add help request for the current user
    
    Request body should contain:
        - course: Course ID
    
    Returns:
        Response: Success message or error
    """
    try:
        # Create a mock POST request for the service
        mock_request = type('MockRequest', (), {
            'POST': request.data,
            'user': request.user
        })()
        
        success, error = add_user_help_request(mock_request)
        
        if success:
            return Response({'message': 'Help request added successfully!'}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error adding help request for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_experience_api(request, experience_id):
    """
    Remove course experience for the current user
    
    Args:
        experience_id: ID of the experience to remove
    
    Returns:
        Response: Success message or error
    """
    try:
        # Create a mock request for the service
        mock_request = type('MockRequest', (), {
            'user': request.user
        })()
        
        success, msg = remove_user_experience(mock_request, experience_id)
        
        if success:
            return Response({'message': msg}, status=status.HTTP_200_OK)
        else:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error removing experience {experience_id} for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_help_request_api(request, help_id):
    """
    Remove help request for the current user
    
    Args:
        help_id: ID of the help request to remove
    
    Returns:
        Response: Success message or error
    """
    try:
        # Create a mock request for the service
        mock_request = type('MockRequest', (), {
            'user': request.user
        })()
        
        success, msg = remove_user_help_request(mock_request, help_id)
        
        if success:
            return Response({'message': msg}, status=status.HTTP_200_OK)
        else:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error removing help request {help_id} for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

