from django.db.models import Q
from django.contrib.postgres.search import TrigramSimilarity
from rest_framework.decorators import api_view
from rest_framework.response import Response

from forum.models import Course
from forum.serializers import UserSerializer
from forum.services.search_services import search_users


def _search_courses(query, limit):
    normalized_query = query.strip().lower()
    if not normalized_query:
        return Course.objects.none()

    return (
        Course.objects.annotate(
            trigram_name=TrigramSimilarity('name', normalized_query),
            trigram_category=TrigramSimilarity('category', normalized_query),
        )
        .filter(
            Q(name__icontains=normalized_query)
            | Q(category__icontains=normalized_query)
            | Q(aliases__name__icontains=normalized_query)
            | Q(trigram_name__gte=0.1)
            | Q(trigram_category__gte=0.1)
        )
        .order_by('-trigram_name', '-trigram_category', 'name')
        .distinct()[:limit]
    )


@api_view(['GET'])
def mentions_autocomplete_api(request):
    query = request.GET.get('query', '').strip()

    try:
        limit = int(request.GET.get('limit', 5))
    except (TypeError, ValueError):
        limit = 5

    limit = max(1, min(limit, 10))

    if not query:
        return Response({'users': [], 'courses': [], 'everyone': []})

    users = search_users(request.user, query)[:limit]
    user_serializer = UserSerializer(users, many=True, context={'request': request})

    courses = _search_courses(query, limit)
    course_results = [
        {
            'id': course.id,
            'name': course.name,
            'category': course.category,
            'type': 'course',
        }
        for course in courses
    ]

    everyone_results = []
    normalized_query = query.lower().lstrip('@')
    if request.user.is_authenticated and getattr(request.user, 'is_teacher', False):
        if 'everyone'.startswith(normalized_query):
            everyone_results.append({
                'id': None,
                'name': 'everyone',
                'type': 'everyone',
            })

    return Response({
        'users': user_serializer.data,
        'courses': course_results,
        'everyone': everyone_results,
    })