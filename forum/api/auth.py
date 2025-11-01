from forum.services.auth_services import (
    authenticate_user,
    register_user,
)
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from forum.forms import CustomUserCreationForm
from forum.services.utils import upload_image
from forum.services.search_services import search_users
from forum.serializers import UserSerializer
import json
from django.utils import timezone
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
    try:
        data = json.loads(request.body)
        school_email = data.get('school_email')
        password = data.get('password')

        if not school_email or not password:
            return JsonResponse({'error': 'Please provide both school email and password'}, status=400)

        user, error = authenticate_user(request, school_email, password)
        if error:
            return JsonResponse({'error': error}, status=401)

        token, _ = Token.objects.get_or_create(user=user)
        
        user_serializer = UserSerializer(user)

        return JsonResponse({
            'token': token.key,
            'user': user_serializer.data
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required
def api_logout(request):
    logout(request)
    return JsonResponse({'success': 'Logged out successfully'})

@csrf_exempt
@require_http_methods(["POST"])
def api_register(request):
    try:
        data = json.loads(request.body)
        form = CustomUserCreationForm(data)
        schedule = data.get('schedule', {})

        if not form.is_valid():
            return JsonResponse({'error': form.errors}, status=400)

        help_needed_courses = data.get('help_needed_courses', [])
        experienced_courses = data.get('experienced_courses', [])
        
        # Get preference settings (default to True if not provided)
        allow_schedule_comparison = data.get('allow_schedule_comparison', True)
        allow_grade_updates = data.get('allow_grade_updates', True)

        user, error = register_user(
            request, form, help_needed_courses, experienced_courses, 
            schedule_data=schedule,
            allow_schedule_comparison=allow_schedule_comparison,
            allow_grade_updates=allow_grade_updates
        )

        if error:
            return JsonResponse({'error': error}, status=400)

        token, _ = Token.objects.get_or_create(user=user)

        user_serializer = UserSerializer(user)

        return JsonResponse({
            'success': True,
            'message': 'Registration successful',
            'data': {
                'auth': {
                    'token': token.key,
                    'token_type': 'Bearer',
                    'expires_in': 86400 * 30,  # 30 days in seconds
                },
                'user': user_serializer.data,
            }
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def search_users_api(request):
    """Search for users API endpoint"""
    try:
        query = request.GET.get('q', '').strip()
        users = search_users(request.user, query)[:10]

        serializer = UserSerializer(users, many=True, context={'request': request})
        
        return Response({'users': serializer.data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_upload_image(request):
    return upload_image(request)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_user_profile_api(request, user_id=None):
    """Get user profile data using serializer"""
    try:
        if user_id:
            from django.shortcuts import get_object_or_404
            from forum.models import User
            user = get_object_or_404(User, id=user_id)
        else:
            user = request.user
            
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_verify_token(request):
    """
    Verify if the current token is valid and return user info
    Useful for iOS apps to check authentication status on app launch
    """
    try:
        user = request.user
        profile = user.userprofile
        
        return JsonResponse({
            'success': True,
            'data': {
                'valid': True,
                'user': {
                    'id': user.id,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': user.get_full_name(),
                    'username': user.username,
                    'school_email': user.school_email,
                    'profile': {
                        'is_moderator': profile.is_moderator,
                        'points': profile.points,
                        'profile_picture_url': profile.profile_picture.url if profile.profile_picture else None,
                        'background_hue': profile.background_hue,
                        'courses': {
                            f'block_{block}': getattr(profile, f'block_{block}').name 
                            for block in ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
                            if getattr(profile, f'block_{block}')
                        }
                    }
                },
                'verified_at': timezone.now().isoformat(),
                'api_version': '1.0'
            }
        })
    except Exception as e:
        logger.error(f"Error verifying token for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'TOKEN_VERIFICATION_ERROR',
                'message': 'Failed to verify token'
            }
        }, status=500)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_refresh_token(request):
    """
    Refresh the user's authentication token
    For enhanced security, especially useful for long-lived iOS apps
    """
    try:
        user = request.user
        
        # Delete old token
        if hasattr(user, 'auth_token'):
            user.auth_token.delete()
        
        # Create new token
        new_token = Token.objects.create(user=user)
        
        logger.info(f"Token refreshed for user {user.id}")
        
        return JsonResponse({
            'success': True,
            'data': {
                'auth': {
                    'token': new_token.key,
                    'token_type': 'Bearer',
                    'expires_in': 86400 * 30,  # 30 days in seconds
                },
                'refreshed_at': timezone.now().isoformat(),
                'api_version': '1.0'
            }
        })
    except Exception as e:
        logger.error(f"Error refreshing token for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'TOKEN_REFRESH_ERROR',
                'message': 'Failed to refresh token'
            }
        }, status=500)

@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_delete_account(request):
    """
    Delete the authenticated user's account
    This is a permanent action that cannot be undone
    """
    try:
        user = request.user
        user_id = user.id
        username = user.username
        
        # Optional: Require password confirmation for extra security
        data = json.loads(request.body) if request.body else {}
        password = data.get('password')
        
        if password:
            # Verify password before deletion
            if not user.check_password(password):
                return JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PASSWORD',
                        'message': 'Invalid password provided'
                    }
                }, status=400)
        
        # Delete the user's token first
        if hasattr(user, 'auth_token'):
            user.auth_token.delete()
        
        # Log the account deletion
        logger.info(f"Account deletion initiated for user {user_id} ({username})")
        
        # Delete the user (this will cascade delete related objects)
        user.delete()
        
        logger.info(f"Account successfully deleted for user {user_id} ({username})")
        
        return JsonResponse({
            'success': True,
            'data': {
                'message': 'Account successfully deleted',
                'deleted_at': timezone.now().isoformat(),
                'api_version': '1.0'
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'INVALID_JSON',
                'message': 'Invalid JSON provided'
            }
        }, status=400)
    except Exception as e:
        logger.error(f"Error deleting account for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': {
                'code': 'ACCOUNT_DELETION_ERROR',
                'message': 'Failed to delete account'
            }
        }, status=500)