from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
import json

from forum.models import Post, Course
from forum.services.feed_services import get_for_you_posts, get_all_posts, paginate_posts
from forum.services.post_services import (
    create_post_service,
    update_post_service,
    delete_post_service,
    get_post_detail_service
)
from forum.serializers import (
    PostListSerializer,
    PostDetailSerializer,
    UserSerializer
)

def convert_string_to_bool(value):
    """Convert string representations of truth to True or False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return bool(value)

def process_post_data_upload(data):
    """Process post data to convert string booleans to actual booleans."""
    processed_data = data.copy()
    
    boolean_fields = ['is_anonymous']
    for field in boolean_fields:
        if field in processed_data:
            processed_data[field] = convert_string_to_bool(processed_data[field])
    
    return processed_data

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def for_you_api(request):
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('limit', 10))

        posts, page_obj = get_for_you_posts(request.user, page, per_page)
        
        serializer = PostListSerializer(posts, many=True, context={'request': request})
        
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
        per_page = int(request.GET.get('limit', 10))
        query = request.GET.get('q', '')

        result = get_all_posts(request.user, query, page, per_page)
        page_obj = result['page_obj']
        
        serializer = PostListSerializer(page_obj.object_list, many=True, context={'request': request})
        
        return Response({
            "posts": serializer.data,
            "has_next": result['has_next'],
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
        serializer = PostDetailSerializer(post, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_post_api(request):
    try:
        processed_data = process_post_data_upload(request.data)
        
        content_json = request.data.get('content')
        content_data = json.loads(content_json) if content_json else {}
        processed_data['content'] = content_data
        
        result = create_post_service(request.user, processed_data)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
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
            status_code = status.HTTP_403_FORBIDDEN if 'permission' in result['error'] else status.HTTP_400_BAD_REQUEST
            return Response(result, status=status_code)
        
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
            return Response(result, status=status.HTTP_403_FORBIDDEN)
        return Response({'message': 'Post deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
