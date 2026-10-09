"""
API endpoints for profile management
"""
import logging
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from forum.services.profile_service import (
    PROFILE_FIELDS,
    get_profile_posts_page,
    update_profile_info,
    update_profile_picture,
    update_lunch_card,
    delete_lunch_card,
    update_privacy_preferences,
    update_profile_courses,
    add_user_experience,
    add_user_help_request,
    remove_user_experience,
    remove_user_help_request,
)

logger = logging.getLogger(__name__)

User = get_user_model()

def _profile_fields(data):
    return {field: data.get(field) for field in PROFILE_FIELDS if field in data}


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
        
        from forum.serializers import PrivateUserSerializer, UserSerializer
        serializer_class = PrivateUserSerializer if profile_user == request.user else UserSerializer
        serializer = serializer_class(profile_user, context={'request': request})
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting profile for {username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_profile_posts_api(request, username):
    """Get paginated posts authored by a profile user (view-compatible behavior)."""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('limit', 3))

        profile_user = get_object_or_404(User, username=username)
        page_obj = get_profile_posts_page(
            viewing_user=request.user,
            profile_user=profile_user,
            page=page,
            per_page=per_page,
        )

        from forum.serializers import PostListSerializer
        serializer = PostListSerializer(page_obj.object_list, many=True, context={'request': request})

        return Response({
            'posts': serializer.data,
            'has_next': page_obj.has_next(),
            'page': page_obj.number,
            'total_pages': page_obj.paginator.num_pages,
            'username': profile_user.username,
            'is_qa_user': profile_user.is_teacher,
        }, status=status.HTTP_200_OK)
    except ValueError:
        return Response({'error': 'Invalid pagination values.'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error getting posts for profile {username}: {str(e)}")
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
        - preferred_msg_app: Preferred contact app (Instagram, LinkedIn, Snapchat, Email, or Discord)
    
    Returns:
        Response: Success message or error
    """
    try:
        form_type = request.data.get('form_type')
        if form_type == 'privacy_preferences':
            allow_schedule_comparison = request.data.get('allow_schedule_comparison')
            display_email = request.data.get('display_email')
            if not isinstance(allow_schedule_comparison, bool) or not isinstance(display_email, bool):
                return Response({
                    'error': 'Privacy preferences must be booleans'
                }, status=status.HTTP_400_BAD_REQUEST)
            result = update_privacy_preferences(
                request.user,
                allow_schedule_comparison=allow_schedule_comparison,
                display_email=display_email,
            )
        else:
            result = update_profile_info(
                request.user, request.user, _profile_fields(request.data)
            )

        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response({'message': result['message']}, status=status.HTTP_200_OK)
            
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
        
        result = update_profile_picture(request.user, request.FILES.get('profile_picture'))
        
        if 'error' not in result:
            return Response({
                'message': result['message'],
                'profile_picture_url': request.user.userprofile.profile_picture.url
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': result['error']
            }, status=result['status'])
        
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
        
        result = update_lunch_card(request.user, request.FILES.get('lunch_card'))
        
        if 'error' not in result:
            return Response({
                'message': result['message'],
                'lunch_card_url': request.user.userprofile.lunch_card.url
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': result['error']
            }, status=result['status'])
        
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
        result = delete_lunch_card(request.user)
        if 'error' not in result:
            return Response({'message': result['message']}, status=status.HTTP_200_OK)
        return Response({'error': result['error']}, status=result['status'])
        
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
        result = update_profile_courses(request.user, request.data)
        
        if 'error' not in result:
            return Response({'message': result['message']}, status=status.HTTP_200_OK)
        else:
            return Response({'error': result['error']}, status=result['status'])
            
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
        result = add_user_experience(request.user, request.data.get('course'))
        
        if 'error' not in result:
            return Response({'message': result['message']}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': result['error']}, status=result['status'])
            
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
        result = add_user_help_request(request.user, request.data.get('course'))
        
        if 'error' not in result:
            return Response({'message': result['message']}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': result['error']}, status=result['status'])
            
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
        result = remove_user_experience(request.user, experience_id)
        
        if 'error' not in result:
            return Response({'message': result['message']}, status=status.HTTP_200_OK)
        else:
            return Response({'error': result['error']}, status=result['status'])
            
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
        result = remove_user_help_request(request.user, help_id)
        
        if 'error' not in result:
            return Response({'message': result['message']}, status=status.HTTP_200_OK)
        else:
            return Response({'error': result['error']}, status=result['status'])
            
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
            "allow_schedule_comparison": bool
        }
    
    Returns:
        Response: Updated user data or error
    """
    try:
        data = request.data
        # Get the boolean values from the request
        allow_schedule_comparison = data.get('allow_schedule_comparison')
        
        # Validate that at least one preference is provided
        if allow_schedule_comparison is None:
            return Response({
                'error': 'At least one preference must be provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(allow_schedule_comparison, bool):
            return Response({
                'error': 'allow_schedule_comparison must be a boolean'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = update_privacy_preferences(
            request.user,
            allow_schedule_comparison=allow_schedule_comparison,
        )
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        
        # Return updated user data using UserSerializer
        from forum.serializers import PrivateUserSerializer
        serializer = PrivateUserSerializer(request.user, context={'request': request})
        
        return Response({
            'message': result['message'],
            'user': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error updating privacy preferences for {request.user.username}: {str(e)}")
        return Response({
            'error': f'An error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
