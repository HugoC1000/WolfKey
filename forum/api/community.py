from datetime import date

from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from forum.serializers import CommunityAccountSerializer, CommunityLunchSerializer, PostListSerializer
from forum.services.community_services import (
    add_community_lunch_service,
    delete_community_lunch_service,
    get_community_lunches_for_date,
    get_owned_community_lunches,
    get_community_directory,
    toggle_community_follow_service,
    toggle_community_subscription_service,
    update_community_lunch_service,
)
from forum.services.feed_services import get_community_posts
from forum.services.poll_display_service import attach_poll_data_to_posts
from forum.services.schedule_services import get_block_order_for_day


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


def _community_lunch_error_response(result):
    error = result['error']
    if error == 'Only active community accounts can manage lunch dates.':
        response_status = status.HTTP_403_FORBIDDEN
    elif error == 'Lunch date not found.':
        response_status = status.HTTP_404_NOT_FOUND
    else:
        response_status = status.HTTP_400_BAD_REQUEST
    return Response({'error': error}, status=response_status)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def community_lunches_api(request):
    """List lunch dates or add one for the current community account."""
    if request.method == 'GET':
        result = get_owned_community_lunches(request.user)
    else:
        result = add_community_lunch_service(
            request.user,
            request.data.get('date'),
            request.data.get('location'),
        )

    if 'error' in result:
        return _community_lunch_error_response(result)
    if request.method == 'POST':
        return Response(
            {'lunch': CommunityLunchSerializer(result['lunch']).data},
            status=status.HTTP_201_CREATED if result['created'] else status.HTTP_200_OK,
        )
    return Response({'lunches': CommunityLunchSerializer(result['lunches'], many=True).data})


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def community_lunches_for_date_api(request, target_date):
    """Return active community lunches for a date when it is a school day."""
    try:
        date_obj = date.fromisoformat(target_date)
        schedule = get_block_order_for_day(target_date)
    except ValueError as exc:
        return Response(
            {'error': 'Invalid date format. Expected YYYY-MM-DD', 'details': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lunches = get_community_lunches_for_date(date_obj, any(schedule.get('blocks', [])))
    return Response({'lunches': CommunityLunchSerializer(lunches, many=True).data})


@api_view(['PATCH', 'DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def community_lunch_detail_api(request, lunch_id):
    if request.method == 'PATCH':
        update_values = {}
        if 'location' in request.data:
            update_values['location'] = request.data.get('location')
        if 'date' in request.data:
            update_values['date_value'] = request.data.get('date')
        result = update_community_lunch_service(request.user, lunch_id, **update_values)
    else:
        result = delete_community_lunch_service(request.user, lunch_id)
    if 'error' in result:
        return _community_lunch_error_response(result)
    if request.method == 'DELETE':
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response({'lunch': CommunityLunchSerializer(result['lunch']).data})


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
