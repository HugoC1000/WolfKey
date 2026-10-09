from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from forum.services.course_services import course_category_class, course_category_color, get_courses_by_block
from forum.services.timetable_services import generate_possible_schedules, get_initial_timetable_data
from forum.views.json_responses import error_payload, success_payload


@login_required
@require_http_methods(["GET"])
def timetable_assigner(request):
    """Render the timetable assigner page and pass initial course selections from the user's profile."""
    data = get_initial_timetable_data(request.user)

    context = {
        'initial_selections_json': json.dumps(data['initial']),
        'allow_schedule_comparison': data['allow_schedule_comparison'],
        'user_grade_level': data['user_grade_level'],
    }
    return render(request, 'forum/timetable_assigner.html', context)


@login_required
@require_http_methods(["GET"])
def all_courses_blocks_view(request):
    try:
        profile = getattr(request.user, 'userprofile', None)
        grade = profile.grade_level if profile and request.GET.get('eligible_only') == '1' else None
        data = get_courses_by_block(grade)
        for links in data['course_links'].values():
            for course in links:
                course['url'] = reverse('course_page', args=[course['id']])
                course['color'] = course_category_color(course['category'])
                course['category_class'] = course_category_class(course['category'])
                del course['category']

        # Keep the established ``blocks`` string-list contract; Atlas uses the
        # parallel link metadata to make its course pills navigable.
        return JsonResponse(success_payload(data))
    except Exception as e:
        return JsonResponse(error_payload(str(e), 500), status=500)


@login_required
@require_http_methods(["POST"])
def generate_schedules_view(request):
    try:
        data = json.loads(request.body)
        requested_course_ids = data.get('requested_course_ids', [])
        if not requested_course_ids:
            return JsonResponse(error_payload('No courses requested'), status=400)

        required_course_ids = data.get('required_course_ids', [])
        schedules = generate_possible_schedules(
            requested_course_ids,
            required_course_ids=required_course_ids,
        )

        return JsonResponse(success_payload({'schedules': schedules}))
    except json.JSONDecodeError:
        return JsonResponse(error_payload('Invalid JSON', error_code='invalid_json'), status=400)
    except Exception as e:
        return JsonResponse(error_payload(str(e), 500), status=500)
