from django.http import JsonResponse
from forum.models import Course, UserCourseExperience, UserCourseHelp
from django.db.models import Q, F, Value, IntegerField, Case, When
from django.db.models.functions import Concat
from django.contrib.postgres.search import TrigramSimilarity
from functools import reduce
from operator import or_

def get_user_courses(user):
    """Get user's experienced and help-needed courses"""
    if not user.is_authenticated:
        return [], []
        
    experienced_courses = Course.objects.filter(
        id__in=UserCourseExperience.objects.filter(
            user=user
        ).values_list('course_id', flat=True)
    )
    
    help_needed_courses = Course.objects.filter(
        id__in=UserCourseHelp.objects.filter(
            user=user,
            active=True
        ).values_list('course_id', flat=True)
    )
    
    return experienced_courses, help_needed_courses


def search_courses(query, limit=10):
    """
    Search for courses by name and aliases using trigram similarity.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results
    
    Returns:
        list[Course]: List of Course objects matching the query
    """
    query = query.strip().lower()
    
    if not query:
        return list(Course.objects.all().distinct()[:limit])
    
    tokens = query.split()

    # Construct similarity annotation (weighted aliases)
    similarity_score = None
    for token in tokens:
        sim = TrigramSimilarity('name', token) + TrigramSimilarity('aliases__name', token) * 1.25
        similarity_score = sim if similarity_score is None else similarity_score + sim

    # Build prefix (istartswith) Q object
    starts_with_q = reduce(
        or_,
        [Q(name__istartswith=token) | Q(aliases__name__istartswith=token) for token in tokens]
    )

    # Build starts_with_score boost: exact prefix match on full query string
    starts_with_score = Case(
        When(name__istartswith=query, then=Value(2)),
        When(aliases__name__istartswith=query, then=Value(3)),
        default=Value(0),
        output_field=IntegerField()
    )

    # First pass: fetch matching IDs with deduplication
    course_ids = Course.objects.annotate(
        similarity=similarity_score,
        starts_with_score=starts_with_score
    ).filter(
        starts_with_q | Q(similarity__gt=0)
    ).order_by(
        '-starts_with_score', '-similarity'
    ).values_list('id', flat=True).distinct()[:limit]

    # Fetch full course objects (deduplicated and ordered)
    courses = Course.objects.filter(id__in=course_ids)
    course_id_list = list(course_ids)  # preserve order
    courses = sorted(courses, key=lambda c: course_id_list.index(c.id))

    # Fallback if nothing matched
    if not courses:
        fallback_filter = reduce(
            or_,
            [Q(name__icontains=token) | Q(aliases__name__icontains=token) for token in tokens]
        )
        fallback_ids = Course.objects.filter(fallback_filter).values_list('id', flat=True).distinct()[:limit]
        courses = Course.objects.filter(id__in=fallback_ids)
        course_id_list = list(fallback_ids)
        courses = sorted(courses, key=lambda c: course_id_list.index(c.id))
    
    return courses


def course_search(request):
    """API endpoint for course search"""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))
    
    courses = search_courses(query, limit)
    
    data = [{
        "id": course.id,
        "name": course.name,
        "category": course.category,
        "experienced_count": UserCourseExperience.objects.filter(course=course).count()
    } for course in courses]

    return JsonResponse(data, safe=False)