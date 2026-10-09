from django.http import JsonResponse

from forum.models import UserCourseExperience
from forum.services.course_services import search_courses


def course_search_api(request):
    """Return course-search results for HTTP clients."""
    query = request.GET.get('q', '').strip()
    try:
        limit = int(request.GET.get('limit', 10))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid limit'}, status=400)

    courses = search_courses(query, limit)
    data = [{
        'id': course.id,
        'name': course.name,
        'category': course.category,
        'experienced_count': UserCourseExperience.objects.filter(course=course).count(),
    } for course in courses]
    return JsonResponse(data, safe=False)
