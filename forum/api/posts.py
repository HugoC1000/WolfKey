from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import json

from forum.models import Post, Course
from forum.services.feed_services import get_for_you_posts, get_all_posts
from django.core.paginator import Paginator
from forum.services.search_services import search_posts
from forum.services.post_services import (
    create_post_service,
    update_post_service,
    delete_post_service,
    like_post_service,
    unlike_post_service,
    follow_post_service,
    unfollow_post_service,
    toggle_community_post_pin_service,
    get_post_share_info_service
)
from forum.services.poll_services import cast_poll_vote, remove_poll_vote
from forum.serializers import (
    PostListSerializer,
    PostDetailSerializer,
    UserSerializer,
    serialize_poll_display_data
)

def convert_string_to_bool(value):
    """Convert string representations of truth to True or False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)

def process_post_data_upload(data):
    """Process post data to convert string booleans to actual booleans and handle multi-value fields."""
    processed_data = data.copy()
    
    if hasattr(data, 'getlist'):
        courses = data.getlist('courses')
        if courses:
            # Convert to integers if they're strings, filter out empty values
            processed_data['courses'] = [
                int(c) if isinstance(c, str) and c.isdigit() else c 
                for c in courses if c
            ]
    boolean_fields = ['is_anonymous', 'allow_teacher']
    for field in boolean_fields:
        if field in processed_data:
            processed_data[field] = convert_string_to_bool(processed_data[field])
    
    # Handle poll_data - parse JSON string if present
    if 'poll_data' in processed_data:
        poll_data_str = processed_data['poll_data']
        try:
            if isinstance(poll_data_str, str):
                processed_data['poll_data'] = json.loads(poll_data_str)
        except (json.JSONDecodeError, TypeError):
            processed_data['poll_data'] = None
    
    return processed_data

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def for_you_api(request):
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('limit', 8))

        page_obj = get_for_you_posts(request.user, page, per_page)
        
        serializer = PostListSerializer(page_obj.object_list, many=True, context={'request': request})
        
        return Response({
            "posts": serializer.data,
            "has_next": page_obj.has_next(),
            "page": page_obj.number,
            "total_pages": page_obj.paginator.num_pages
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def all_posts_api(request):
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('limit', 8))
        query = request.GET.get('q', '')

        page_obj = get_all_posts(request.user, query, page, per_page)
        
        serializer = PostListSerializer(page_obj.object_list, many=True, context={'request': request})
        
        return Response({
            "posts": serializer.data,
            "has_next": page_obj.has_next(),
            "page": page_obj.number,
            "total_pages": page_obj.paginator.num_pages,
            "query": query
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def post_detail_api(request, post_id):
    try:
        post = get_object_or_404(Post, id=post_id)
        
        # Check teacher visibility
        if request.user.is_authenticated and request.user.is_teacher and not post.allow_teacher:
            return Response(
                {'error': "You don't have permission to view this post."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = PostDetailSerializer(post, context={'request': request})
        post.views += 1
        post.save()
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_post_api(request):
    try:
        print("Request data, " , request.data)
        processed_data = process_post_data_upload(request.data)
        
        # Parse content
        content_json = request.data.get('content')
        content_data = json.loads(content_json) if content_json else {}
        processed_data['content'] = content_data

        print(processed_data)
        
        result = create_post_service(request.user, processed_data)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        
        post = Post.objects.get(id=result['id'])
        serializer = PostDetailSerializer(post, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT', 'PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_post_api(request, post_id):
    try:
        processed_data = process_post_data_upload(request.data)
        
        content_json = request.data.get('content')
        if content_json:
            content_data = json.loads(content_json)
            processed_data['content'] = content_data
        
        result = update_post_service(request.user, post_id, processed_data)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        
        post = Post.objects.get(id=post_id)
        serializer = PostDetailSerializer(post, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_post_api(request, post_id):
    try:
        result = delete_post_service(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response({'message': 'Post deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def toggle_community_post_pin_api(request, post_id):
    result = toggle_community_post_pin_service(request.user, post_id)
    if 'error' in result:
        return Response({'error': result['error']}, status=result['status'])
    return Response(result)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def like_post_api(request, post_id):
    """
    API endpoint to like a post
    """
    try:
        result = like_post_service(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def unlike_post_api(request, post_id):
    """
    API endpoint to unlike a post
    """
    try:
        result = unlike_post_service(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def follow_post_api(request, post_id):
    """
    API endpoint to follow a post
    """
    try:
        result = follow_post_service(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def unfollow_post_api(request, post_id):
    """
    API endpoint to unfollow a post
    """
    try:
        result = unfollow_post_service(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_post_share_info_api(request, post_id):
    """
    API endpoint to get post share information
    """
    try:
        result = get_post_share_info_service(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        result['post_url'] = request.build_absolute_uri(result['post_url'])
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def vote_on_poll_api(request, post_id):
    """
    API endpoint to vote on a poll
    """
    try:
        result = cast_poll_vote(request.user, post_id, request.data.get('selected_option_ids', []))
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        poll = result['poll']
        poll_data = serialize_poll_display_data(poll, viewer=request.user) or {}
        
        return Response({
            'success': True,
            'message': result['message'],
            **poll_data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def remove_poll_vote_api(request, post_id):
    """
    API endpoint to remove a vote from a poll
    """
    try:
        result = remove_poll_vote(request.user, post_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        poll = result['poll']
        poll_data = serialize_poll_display_data(poll, viewer=request.user) or {}

        return Response({
            'success': True,
            'message': result['message'],
            **poll_data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def search_posts_api(request):
    """Search for posts API endpoint"""
    try:
        query = request.GET.get('q', '').strip()
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('limit', 8))
        
        posts = search_posts(request.user, query)
        page_obj = Paginator(posts, per_page).get_page(page)
        
        serializer = PostListSerializer(page_obj.object_list, many=True, context={'request': request})
        
        return Response({
            'posts': serializer.data,
            'has_next': page_obj.has_next(),
            'page': page_obj.number,
            'total_pages': page_obj.paginator.num_pages,
            'query': query
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
