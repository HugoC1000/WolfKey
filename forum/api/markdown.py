"""Versioned content API. The existing /api/ routes keep Editor.js JSON."""

from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from forum.api.posts import process_post_data_upload
from forum.api.pagination import feed_pagination
from forum.models import Comment, Post, Solution
from forum.serializers import CommentSerializer, PostDetailSerializer, PostListSerializer, SolutionSerializer
from forum.services.feed_services import get_all_posts, get_for_you_posts
from forum.services.comment_services import (
    create_comment_service, delete_comment_service, edit_comment_service,
    get_comments_service,
)
from forum.services.post_services import (
    _check_teacher_visibility, create_post_service, delete_post_service,
    update_post_service,
)
from forum.services.solution_services import (
    create_solution_service, delete_solution_service, update_solution_service,
)


def _context(request):
    return {'request': request, 'content_format': 'markdown'}


def _result_error(result):
    return Response({'error': result['error']}, status=result.get('status', 400))


def _markdown_data(request, *, require_content=True):
    content = request.data.get('content')
    if require_content and (not isinstance(content, str) or not content.strip()):
        return None, Response({'error': 'Markdown content is required.'}, status=400)
    if 'content' in request.data and not isinstance(content, str):
        return None, Response({'error': 'Markdown content must be a string.'}, status=400)
    values = request.data.copy()
    values['content_format'] = 'markdown'
    return values, None


def _post_feed_response(request, page_obj, *, query=None):
    data = {
        'posts': PostListSerializer(page_obj.object_list, many=True,
                                    context={'request': request}).data,
        'has_next': page_obj.has_next(),
        'page': page_obj.number,
        'total_pages': page_obj.paginator.num_pages,
    }
    if query is not None:
        data['query'] = query
    return Response(data)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def all_posts_markdown_api(request):
    page, limit = feed_pagination(request)
    query = request.GET.get('q', '')
    page_obj = get_all_posts(request.user, query, page, limit)
    return _post_feed_response(request, page_obj, query=query)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def for_you_markdown_api(request):
    page, limit = feed_pagination(request)
    page_obj = get_for_you_posts(request.user, page, limit)
    return _post_feed_response(request, page_obj)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def post_detail_markdown_api(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    try:
        _check_teacher_visibility(request.user, post)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=403)
    Post.objects.filter(id=post_id).update(views=F('views') + 1)
    post.views += 1
    return Response(PostDetailSerializer(post, context=_context(request)).data)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_post_markdown_api(request):
    values, error = _markdown_data(request, require_content=False)
    if error:
        return error
    values.setdefault('content', '')
    values = process_post_data_upload(values)
    result = create_post_service(request.user, values)
    if 'error' in result:
        return _result_error(result)
    post = Post.objects.get(id=result['id'])
    return Response(PostDetailSerializer(post, context=_context(request)).data,
                    status=status.HTTP_201_CREATED)


@api_view(['PUT', 'PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_post_markdown_api(request, post_id):
    values, error = _markdown_data(request, require_content=False)
    if error:
        return error
    values = process_post_data_upload(values)
    result = update_post_service(request.user, post_id, values)
    if 'error' in result:
        return _result_error(result)
    post = Post.objects.get(id=post_id)
    return Response(PostDetailSerializer(post, context=_context(request)).data)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_post_markdown_api(request, post_id):
    result = delete_post_service(request.user, post_id)
    if 'error' in result:
        return _result_error(result)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_solution_markdown_api(request, post_id):
    values, error = _markdown_data(request)
    if error:
        return error
    result = create_solution_service(request.user, post_id, values)
    if 'error' in result:
        return _result_error(result)
    solution = Solution.objects.get(id=result['id'])
    return Response(SolutionSerializer(solution, context=_context(request)).data,
                    status=status.HTTP_201_CREATED)


@api_view(['PUT', 'PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_solution_markdown_api(request, solution_id):
    values, error = _markdown_data(request)
    if error:
        return error
    result = update_solution_service(request.user, solution_id, values)
    if 'error' in result:
        return _result_error(result)
    solution = Solution.objects.get(id=solution_id)
    return Response(SolutionSerializer(solution, context=_context(request)).data)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_solution_markdown_api(request, solution_id):
    result = delete_solution_service(request.user, solution_id)
    if 'error' in result:
        return _result_error(result)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_comment_markdown_api(request, solution_id):
    values, error = _markdown_data(request)
    if error:
        return error
    result = create_comment_service(request.user, solution_id, values)
    if 'error' in result:
        return _result_error(result)
    comment = Comment.objects.get(id=result['id'])
    return Response(CommentSerializer(comment, context=_context(request)).data,
                    status=status.HTTP_201_CREATED)


@api_view(['PUT', 'PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_comment_markdown_api(request, comment_id):
    values, error = _markdown_data(request)
    if error:
        return error
    result = edit_comment_service(request.user, comment_id, values)
    if 'error' in result:
        return _result_error(result)
    comment = Comment.objects.get(id=comment_id)
    return Response(CommentSerializer(comment, context=_context(request)).data)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_comment_markdown_api(request, comment_id):
    result = delete_comment_service(request.user, comment_id)
    if 'error' in result:
        return _result_error(result)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def comments_markdown_api(request, solution_id):
    result = get_comments_service(request.user, solution_id)
    if 'error' in result:
        return _result_error(result)
    roots = [comment for comment in result['comments'] if comment.parent_id is None]
    return Response({
        'comments': CommentSerializer(roots, many=True, context=_context(request)).data,
        'solution_id': solution_id,
    })
