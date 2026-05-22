"""
Mention search views for both web and API endpoints
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from forum.services.mention_service import search_mentions


@require_http_methods(["GET"])
@login_required
def mention_search(request):
    """
    Web view for mention autocomplete searches.
    
    Requires user to be logged in via session.
    Called from JavaScript editor with ?query=...&trigger=...&limit=...
    
    Query parameters:
    - query: Search string (required)
    - trigger: '@' for users/everyone, '#' for courses (optional)
    - limit: Max results per category (default: 5)
    
    Returns JSON: {users: [...], courses: [...], everyone: [...]}
    """
    try:
        query = request.GET.get('query', '').strip()
        trigger = request.GET.get('trigger', '').strip()
        limit = int(request.GET.get('limit', 5))
        
        if not query:
            return JsonResponse({
                'users': [],
                'courses': [],
                'everyone': []
            })
        
        # request.user is authenticated because of @login_required
        results = search_mentions(request.user, query, limit, trigger=trigger)
        
        return JsonResponse(results)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
