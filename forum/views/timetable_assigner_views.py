from django.shortcuts import render
from django.views.decorators.http import require_http_methods
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from forum.serializers.user import USER_SCHEDULE_BLOCKS
from forum.services.course_services import filter_courses_for_grade
from forum.services.timetable_services import generate_possible_schedules


@login_required
@require_http_methods(["GET"])
def timetable_assigner(request):
    """Render the timetable assigner page and pass initial course selections from the user's profile."""
    user = request.user
    profile = getattr(user, 'userprofile', None)

    blocks = USER_SCHEDULE_BLOCKS
    initial = {}

    if profile:
        for b in blocks:
            course = getattr(profile, f'block_{b}', None)
            if course and getattr(course, 'name', None) and 'study' not in course.name.lower():
                initial[b] = {
                    'id': course.id,
                    'name': course.name,
                    'category': course.category if hasattr(course, 'category') else 'Misc',
                    'experienced_count': 0
                }
            else:
                initial[b] = None
    else:
        for b in blocks:
            initial[b] = None

    context = {
        'initial_selections_json': json.dumps(initial),
        'allow_schedule_comparison': bool(profile and profile.allow_schedule_comparison),
        'user_grade_level': profile.grade_level if profile else None,
    }
    return render(request, 'forum/timetable_assigner.html', context)


@login_required
@require_http_methods(["GET"])
def all_courses_blocks_view(request):
    try:
        # Reuse the API logic but return JsonResponse for session users
        from forum.models import Course
        blocks_data = {block_code: [] for block_code in USER_SCHEDULE_BLOCKS}

        courses_qs = Course.objects.prefetch_related('blocks').all()
        if request.GET.get('eligible_only') == '1':
            profile = getattr(request.user, 'userprofile', None)
            courses_qs = filter_courses_for_grade(
                courses_qs,
                profile.grade_level if profile else None,
            )
        for course in courses_qs:
            for block in course.blocks.all():
                if block.code in blocks_data:
                    blocks_data[block.code].append(course.name)

        return JsonResponse({'success': True, 'blocks': blocks_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def generate_schedules_view(request):
    try:
        data = json.loads(request.body)
        requested_course_ids = data.get('requested_course_ids', [])
        if not requested_course_ids:
            return JsonResponse({'error': 'No courses requested'}, status=400)

        required_course_ids = data.get('required_course_ids', [])
        schedules = generate_possible_schedules(
            requested_course_ids,
            required_course_ids=required_course_ids,
        )

        return JsonResponse({'success': True, 'schedules': schedules})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
