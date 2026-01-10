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
    update_lunch_card,
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
        
        # Use UserSerializer which includes UserProfileSerializer
        from forum.serializers import UserSerializer
        serializer = UserSerializer(profile_user, context={'request': request})
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
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
        - instagram_handle: Instagram username (without @)
        - snapchat_handle: Snapchat username (without @)
        - linkedin_url: LinkedIn profile URL (must start with www.linkedin.com/in/)
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


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def upload_lunch_card_api(request):
    """
    Upload lunch card for the current user
    
    Request should contain a file in 'lunch_card' field
    
    Returns:
        Response: Success message and new lunch card URL or error
    """
    try:
        if 'lunch_card' not in request.FILES:
            return Response({
                'error': 'No lunch card file provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create a mock request for the service
        mock_request = type('MockRequest', (), {
            'FILES': request.FILES,
            'user': request.user
        })()
        
        update_lunch_card(mock_request)
        
        return Response({
            'message': 'Lunch card uploaded successfully!',
            'lunch_card_url': request.user.userprofile.lunch_card.url
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error uploading lunch card for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_lunch_card_api(request):
    """
    Delete lunch card for the current user
    
    Returns:
        Response: Success message or error
    """
    try:
        profile = request.user.userprofile
        
        if not profile.lunch_card:
            return Response({
                'error': 'No lunch card to delete'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete the lunch card file
        profile.lunch_card.delete(save=True)
        
        return Response({
            'message': 'Lunch card deleted successfully!'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error deleting lunch card for {request.user.username}: {str(e)}")
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


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_privacy_preferences_api(request):
    """
    Update privacy preferences for the current user
    
    Request body:
        {
            "allow_schedule_comparison": bool,
            "allow_grade_updates": bool
        }
    
    Returns:
        Response: Updated user data or error
    """
    try:
        data = request.data
        profile_user = request.user
        
        # Get the boolean values from the request
        allow_schedule_comparison = data.get('allow_schedule_comparison')
        allow_grade_updates = data.get('allow_grade_updates')
        
        # Validate that at least one preference is provided
        if allow_schedule_comparison is None and allow_grade_updates is None:
            return Response({
                'error': 'At least one preference must be provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update the preferences
        if allow_schedule_comparison is not None:
            profile_user.userprofile.allow_schedule_comparison = allow_schedule_comparison
        
        if allow_grade_updates is not None:
            profile_user.userprofile.allow_grade_updates = allow_grade_updates
        
        profile_user.userprofile.save()
        
        # Return updated user data using UserSerializer
        from forum.serializers import UserSerializer
        serializer = UserSerializer(profile_user, context={'request': request})
        
        return Response({
            'message': 'Privacy preferences updated successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error updating privacy preferences for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
