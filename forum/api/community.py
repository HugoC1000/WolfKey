from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from forum.serializers import CommunityAccountSerializer, PostListSerializer
from forum.services.community_services import (
    get_community_directory,
    toggle_community_follow_service,
    toggle_community_subscription_service,
)
from forum.services.feed_services import get_community_posts
from forum.services.poll_display_service import attach_poll_data_to_posts


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def community_accounts_api(request):
    """List active communities with the requesting user's membership state."""
    communities, followed_ids, subscribed_ids = get_community_directory(request.user)
    serializer = CommunityAccountSerializer(communities, many=True, context={
        'followed_community_ids': followed_ids,
        'subscribed_community_ids': subscribed_ids,
    })
    return Response({'communities': serializer.data})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def community_posts_api(request):
    page_obj = get_community_posts(request.user, request.GET.get('page', 1), request.GET.get('limit', 8))
    posts = list(page_obj.object_list)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)
    return Response({
        'posts': posts_data,
        'has_next': page_obj.has_next(),
        'page': page_obj.number,
        'total_pages': page_obj.paginator.num_pages,
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def toggle_community_follow_api(request, community_id):
    result = toggle_community_follow_service(request.user, community_id)
    if 'error' in result:
        return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'following': result['following'],
        'mailing_list_joined': result['mailing_list_joined'],
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def toggle_community_subscription_api(request, community_id):
    result = toggle_community_subscription_service(request.user, community_id)
    if 'error' in result:
        return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'subscribed': result['subscribed']})
