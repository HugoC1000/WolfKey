"""
API endpoints for mobile notifications
"""
import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from forum.models import Notification
from forum.services.notification_services import (
    all_notifications_service,
    mark_notification_read_service
)

logger = logging.getLogger(__name__)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def notifications_api(request):
    """
    Get all notifications for the authenticated user
    """
    try:
        from forum.services.deep_link_service import create_notification_deep_link
        
        notifications = all_notifications_service(request.user)
        
        notification_data = []
        for notification in notifications:
            # deep link data 
            deep_link_data = create_notification_deep_link(
                notification_type=notification.notification_type,
                post=notification.post,
                solution=notification.solution,
                post_id=notification.post.id if notification.post else None,
                solution_id=notification.solution.id if notification.solution else None,
                user=notification.sender
            )
            
            data = {
                'id': notification.id,
                'notification_type': notification.notification_type,
                'message': notification.message,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'sender': {
                    'id': notification.sender.id,
                    'full_name': notification.sender.get_full_name(),
                    'username': notification.sender.username
                } if notification.sender else None,
                'post': {
                    'id': notification.post.id,
                    'title': notification.post.title
                } if notification.post else None,
                'solution': {
                    'id': notification.solution.id
                } if notification.solution else None,
                'deep_link': deep_link_data 
            }
            notification_data.append(data)
        
        return Response({
            'success': True,
            'data': {
                'notifications': notification_data,
                'unread_count': notifications.filter(is_read=False).count()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching notifications for user {request.user.id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to fetch notifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def unread_count_api(request):
    """
    Get the count of unread notifications for the authenticated user
    Lightweight endpoint for badge counts and notification indicators
    """
    try:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

        return Response({
            'success': True,
            'data': {
                'unread_count': unread_count
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching unread count for user {request.user.id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to fetch unread count'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mark_notification_read_api(request, notification_id):
    """
    Mark a specific notification as read
    """
    try:
        notification = mark_notification_read_service(request.user, notification_id)
        
        return Response({
            'success': True,
            'data': {
                'notification_id': notification.id,
                'is_read': notification.is_read
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to mark notification as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read_api(request):
    """
    Mark all notifications as read for the authenticated user
    """
    try:
        notifications = all_notifications_service(request.user)
        unread_notifications = notifications.filter(is_read=False)
        
        for notification in unread_notifications:
            mark_notification_read_service(request.user, notification.id)
        
        return Response({
            'success': True,
            'data': {
                'marked_count': unread_notifications.count()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read for user {request.user.id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to mark all notifications as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def register_push_token_api(request):
    """
    Register or update the user's Expo push notification token
    """
    try:
        push_token = request.data.get('push_token')
        if not push_token:
            return Response({
                'success': False,
                'error': 'Push token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Store the push token in user profile
        user_profile = request.user.userprofile
        user_profile.expo_push_token = push_token
        user_profile.save()
        
        logger.info(f"Registered push token for user {request.user.id}")
        
        return Response({
            'success': True,
            'data': {
                'message': 'Push token registered successfully'
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error registering push token for user {request.user.id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to register push token'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def unregister_push_token_api(request):
    """
    Unregister the user's Expo push notification token
    """
    try:
        # Remove the push token from user profile
        user_profile = request.user.userprofile
        user_profile.expo_push_token = None
        user_profile.save()
        
        logger.info(f"Unregistered push token for user {request.user.id}")
        
        return Response({
            'success': True,
            'data': {
                'message': 'Push token unregistered successfully'
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error unregistering push token for user {request.user.id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to unregister push token'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mark_notifications_by_post_api(request, post_id):
    """
    Mark all notifications associated with a specific post as read for the authenticated user
    """
    try:
        from forum.models import Post
        
        # Verify the post exists
        try:
            post = Post.objects.get(id=post_id)
        except Post.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Post not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Find all unread notifications for this user related to this post
        unread_notifications = Notification.objects.filter(
            recipient=request.user,
            post=post,
            is_read=False
        )
        
        marked_count = unread_notifications.count()
        
        # Mark them all as read
        unread_notifications.update(is_read=True)
        
        logger.info(f"Marked {marked_count} notifications as read for user {request.user.id} on post {post_id}")
        
        return Response({
            'success': True,
            'data': {
                'marked_count': marked_count,
                'post_id': post_id
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error marking notifications by post {post_id} for user {request.user.id}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to mark notifications as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
