from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from forum.models import Comment, Solution
from forum.services.comment_services import (
    create_comment_service,
    edit_comment_service,
    delete_comment_service,
    get_comments_service,
)
from forum.serializers import CommentSerializer

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_comment_api(request, solution_id):
    try:
        result = create_comment_service(request, solution_id, request.data)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        comment = Comment.objects.get(id=result['id'])
        serializer = CommentSerializer(comment, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        print(e)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT', 'PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def edit_comment_api(request, comment_id):
    try:
        result = edit_comment_service(request, comment_id, request.data)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        comment = Comment.objects.get(id=comment_id)
        serializer = CommentSerializer(comment, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_comment_api(request, comment_id):
    try:
        result = delete_comment_service(request, comment_id)
        if 'error' in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Comment deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_comments_api(request, solution_id):
    try:
        solution = get_object_or_404(Solution, id=solution_id)
        comments = solution.comments.filter(parent__isnull=True).order_by('created_at')
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response({
            'comments': serializer.data,
            'solution_id': solution_id
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)