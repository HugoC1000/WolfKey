from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from forum.serializers import CourseRosterStudentSerializer
from forum.services.course_hub_service import (
    contribute_course_teacher as contribute_teacher_service,
    edit_course_teacher as edit_teacher_service,
    get_course_hub,
)
from forum.services.course_services import course_category_class, course_category_color


@login_required
def course_page(request, course_id):
    result = get_course_hub(request.user, course_id)
    if 'error' in result:
        raise Http404(result['error'])
    course = result['course']
    context = {
        'course': course,
        'course_color': course_category_color(course.category),
        'course_category_class': course_category_class(course.category),
    }
    if not result['access_granted']:
        context.update({
            'has_uploaded_schedule': result['has_uploaded_schedule'],
            'allow_schedule_comparison': result['allow_schedule_comparison'],
        })
        return render(request, 'forum/course_access_required.html', context)

    context.update({
        'posts': result['posts'],
        'roster_blocks': [
            {
                **block,
                'students': CourseRosterStudentSerializer(block['students'], many=True).data,
            }
            for block in result['blocks']
        ],
    })
    return render(request, 'forum/course_page.html', context)


def _teacher_action_response(request, result, course_id):
    if 'error' in result:
        return HttpResponse(result['error'], status=result['status'])
    (messages.info if result['duplicate'] else messages.success)(request, result['message'])
    return redirect('course_page', course_id=course_id)


@login_required
@require_POST
def contribute_course_teacher(request, course_id):
    result = contribute_teacher_service(
        request.user, course_id, request.POST.get('block'), request.POST.get('teacher_name'),
    )
    return _teacher_action_response(request, result, course_id)


@login_required
@require_POST
def edit_course_teacher(request, course_id, report_id):
    result = edit_teacher_service(
        request.user, course_id, report_id, request.POST.get('teacher_name'),
    )
    return _teacher_action_response(request, result, course_id)
