from django.shortcuts import render
from django.views.decorators.http import require_http_methods
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from forum.services.timetable_services import generate_possible_schedules, evaluate_multiple_schedules



@require_http_methods(["GET"])
def timetable_assigner(request):
    """Render the timetable assigner page and pass initial course selections from the user's profile."""
    user = request.user
    profile = getattr(user, 'userprofile', None)

    blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
    initial = {}

    if profile:
        # Map profile FK fields to blocks
        mapping = {
            '1A': profile.block_1A,
            '1B': profile.block_1B,
            '1D': profile.block_1D,
            '1E': profile.block_1E,
            '2A': profile.block_2A,
            '2B': profile.block_2B,
            '2C': profile.block_2C,
            '2D': profile.block_2D,
            '2E': profile.block_2E,
        }

        for b in blocks:
            course = mapping.get(b)
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
        'initial_selections_json': json.dumps(initial)
    }
    return render(request, 'forum/timetable_assigner.html', context)


@require_http_methods(["GET"])
def all_courses_blocks_view(request):
    try:
        # Reuse the API logic but return JsonResponse for session users
        from forum.models import Course
        all_blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        blocks_data = {block_code: [] for block_code in all_blocks}

        courses_qs = Course.objects.prefetch_related('blocks').all()
        for course in courses_qs:
            for block in course.blocks.all():
                if block.code in blocks_data:
                    blocks_data[block.code].append(course.name)

        return JsonResponse({'success': True, 'blocks': blocks_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_schedules_view(request):
    try:
        data = json.loads(request.body)
        requested_course_ids = data.get('requested_course_ids', [])
        if not requested_course_ids:
            return JsonResponse({'error': 'No courses requested'}, status=400)

        required_course_ids = data.get('required_course_ids', [])
        schedules = generate_possible_schedules(requested_course_ids, required_course_ids=required_course_ids)
        return JsonResponse({'success': True, 'schedules': schedules})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
