from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from forum.models import Solution
from forum.services.solution_services import (
    create_solution_service,
    update_solution_service,
    delete_solution_service,
    vote_solution_service,
    accept_solution_service
)
from forum.serializers import SolutionSerializer

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_solution_api(request, post_id):
    try:
        result = create_solution_service(request.user, post_id, request.data)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        
        solution = Solution.objects.get(id=result['id'])
        serializer = SolutionSerializer(solution, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT', 'PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_solution_api(request, solution_id):
    try:
        result = update_solution_service(request.user, solution_id, request.data)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        
        solution = Solution.objects.get(id=solution_id)
        serializer = SolutionSerializer(solution, context={'request': request})
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_solution_api(request, solution_id):
    try:
        result = delete_solution_service(request.user, solution_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response({'message': 'Solution deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def vote_solution_api(request, solution_id):
    try:
        vote_type = request.data.get('vote_type')
        if vote_type not in ['upvote', 'downvote']:
            return Response({'error': 'Invalid vote type'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = vote_solution_service(request.user, solution_id, vote_type)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def accept_solution_api(request, solution_id):
    try:
        result = accept_solution_service(request.user, solution_id)
        if 'error' in result:
            return Response({'error': result['error']}, status=result['status'])
        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
