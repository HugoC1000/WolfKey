"""
API endpoints for mentions autocomplete
Supports searching for users, courses, and "everyone" (admin-only)
"""

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from forum.services.mention_service import search_mentions


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def mentions_autocomplete_api(request):
    """
    API endpoint for mention autocomplete searches.
    
    Requires token authentication.
    
    Query parameters:
    - query: Search string (required)
    - trigger: '@' for users/everyone, '#' for courses (optional, searches all if not provided)
    - limit: Max results per category (default: 5)
    
    Response format:
    {
        "users": [...],
        "courses": [...],
        "everyone": [...]
    }
    """
    try:
        query = request.GET.get('query', '').strip()
        trigger = request.GET.get('trigger', '').strip()  # '@' or '#'
        limit = int(request.GET.get('limit', 5))
        
        if not query:
            return Response({
                'users': [],
                'courses': [],
                'everyone': []
            }, status=status.HTTP_200_OK)
        
        # request.user is authenticated because of @permission_classes([IsAuthenticated])
        results = search_mentions(request.user, query, limit, trigger=trigger)
        
        return Response(results, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
