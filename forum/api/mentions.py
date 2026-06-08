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


def _parse_limit(request, default=5):
    try:
        limit = int(request.GET.get('limit', default))
    except (TypeError, ValueError):
        limit = default

    return max(1, min(limit, 10))


def _everyone_results(request, query):
    everyone_results = []
    normalized_query = query.lower().lstrip('@')

    if request.user.is_authenticated and getattr(request.user, 'is_teacher', False):
        if 'everyone'.startswith(normalized_query):
            everyone_results.append({
                'id': None,
                'name': 'everyone',
                'type': 'everyone',
            })

    return everyone_results


def _mentions_users_payload(request):
    query = request.GET.get('query', '').strip()
    limit = _parse_limit(request)

    if not query:
        return Response({'users': [], 'everyone': []})

    users = search_users(request.user, query)[:limit]
    user_serializer = UserSerializer(users, many=True, context={'request': request})

    return Response({
        'users': user_serializer.data,
        'everyone': _everyone_results(request, query),
    })


def _mentions_courses_payload(request):
    query = request.GET.get('query', '').strip()
    limit = _parse_limit(request)

    if not query:
        return Response({'courses': []})

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

    return Response({'courses': course_results})


@api_view(['GET'])
def mentions_users_autocomplete_api(request):
    return _mentions_users_payload(request)


@api_view(['GET'])
def mentions_courses_autocomplete_api(request):
    return _mentions_courses_payload(request)


@api_view(['GET'])
def mentions_autocomplete_api(request):
    query = request.GET.get('query', '').strip()

    if not query:
        return Response({'users': [], 'courses': [], 'everyone': []})

    users_response = _mentions_users_payload(request).data
    courses_response = _mentions_courses_payload(request).data

    return Response({
        'users': users_response.get('users', []),
        'courses': courses_response.get('courses', []),
        'everyone': users_response.get('everyone', []),
    })
