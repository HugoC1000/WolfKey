from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import Coalesce
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from forum.models import Course, CourseTeacher, Post, UserProfile
from forum.serializers import PostListSerializer
from forum.serializers.user import USER_SCHEDULE_BLOCKS, safe_file_url
from forum.services.course_services import course_category_class, course_category_color
from forum.services.poll_display_service import attach_poll_data_to_posts
from forum.services.utils import annotate_post_card_context


def _has_uploaded_schedule(profile):
    return any(getattr(profile, f'block_{block}_id') for block in USER_SCHEDULE_BLOCKS)


def _can_access_course_hub(user):
    if user.is_staff:
        return True
    profile = getattr(user, 'userprofile', None)
    return bool(
        profile
        and profile.allow_schedule_comparison
        and _has_uploaded_schedule(profile)
    )


def _can_manage_block_teacher(user, course, block):
    if user.is_staff:
        return True
    if block not in USER_SCHEDULE_BLOCKS:
        return False
    if not _can_access_course_hub(user):
        return False
    return getattr(user.userprofile, f'block_{block}_id', None) == course.id


def _serialize_roster_student(profile):
    """Return only the public identity fields needed by the course roster."""
    user = profile.user
    full_name = user.get_full_name().strip() or user.username
    initials = ''.join(part[0] for part in full_name.split()[:2]).upper()
    picture = profile.profile_picture
    picture_url = None
    if picture and picture.name != 'profile_pictures/default.png':
        picture_url = safe_file_url(picture)
    return {
        'username': user.username,
        'full_name': full_name,
        'initials': initials,
        'profile_picture_url': picture_url,
    }


@login_required
def course_page(request, course_id):
    """Show the shared class hub: students, teacher reports, and course posts."""
    course = get_object_or_404(Course, id=course_id)
    profile = request.user.userprofile
    has_uploaded_schedule = _has_uploaded_schedule(profile)
    if not _can_access_course_hub(request.user):
        return render(request, 'forum/course_access_required.html', {
            'course': course,
            'course_color': course_category_color(course.category),
            'course_category_class': course_category_class(course.category),
            'has_uploaded_schedule': has_uploaded_schedule,
            'allow_schedule_comparison': profile.allow_schedule_comparison,
        })

    blocks_by_code = {block.code: block for block in course.blocks.all()}
    course_blocks = [blocks_by_code[code] for code in USER_SCHEDULE_BLOCKS if code in blocks_by_code]

    # A student's roster membership comes from their saved timetable. Respect the
    # schedule-comparison privacy setting and expose only names, never contact data.
    student_profiles = UserProfile.objects.filter(
        allow_schedule_comparison=True,
        user__is_teacher=False,
    ).select_related('user')
    students_by_block = defaultdict(list)
    for block in course_blocks:
        field_name = f'block_{block.code}'
        students_by_block[block.code] = [
            profile for profile in student_profiles.filter(**{field_name: course}).order_by(
                'user__first_name', 'user__last_name'
            )
        ]
    reports = list(
        CourseTeacher.objects.filter(course=course)
        .order_by('block', 'teacher_name')
    )
    reports_by_block = defaultdict(list)
    for report in reports:
        report.can_manage = _can_manage_block_teacher(
            request.user, course, report.block,
        )
        reports_by_block[report.block].append(report)

    posts = Post.objects.filter(courses=course)
    if request.user.is_teacher:
        posts = posts.filter(allow_teacher=True)
    posts = list(
        posts.annotate(
            solution_count=Count('solutions', distinct=True),
            comment_count=Count('solutions__comments', distinct=True),
            total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True),
            recent_updated_at=Coalesce('last_activity_at', 'created_at'),
        )
        .select_related('author', 'author__userprofile')
        .prefetch_related('courses')
        .order_by('-recent_updated_at', '-created_at')
    )
    annotate_post_card_context(posts, request.user)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)

    roster_blocks = [
        {
            'code': block.code,
            'reports': reports_by_block[block.code],
            'can_contribute': _can_manage_block_teacher(request.user, course, block.code),
            'students': [
                _serialize_roster_student(student)
                for student in students_by_block[block.code]
            ],
        }
        for block in course_blocks
    ]

    return render(request, 'forum/course_page.html', {
        'course': course,
        'roster_blocks': roster_blocks,
        'posts': posts,
        'course_color': course_category_color(course.category),
        'course_category_class': course_category_class(course.category),
    })


@login_required
@require_POST
def contribute_course_teacher(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    block = (request.POST.get('block') or '').strip().upper()
    teacher_name = ' '.join((request.POST.get('teacher_name') or '').split())
    if not course.blocks.filter(code=block).exists() or not teacher_name or len(teacher_name) > 100:
        return HttpResponseBadRequest('Enter a valid block and teacher name.')
    if not _can_manage_block_teacher(request.user, course, block):
        return HttpResponseForbidden('You must share this class to update its teacher information.')

    report = CourseTeacher.objects.filter(
        course=course, block=block, teacher_name__iexact=teacher_name,
    ).first()
    if report is None:
        CourseTeacher.objects.create(
            course=course, block=block, teacher_name=teacher_name,
        )
        messages.success(request, f'Added {teacher_name} for {block}.')
    else:
        messages.info(request, f'{teacher_name} is already listed for {block}.')
    return redirect('course_page', course_id=course_id)


@login_required
@require_POST
def edit_course_teacher(request, course_id, report_id):
    """Let the class community correct a teacher name."""
    report = get_object_or_404(CourseTeacher, id=report_id, course_id=course_id)
    if not _can_manage_block_teacher(request.user, report.course, report.block):
        return HttpResponseForbidden('You must share this class to update its teacher information.')
    teacher_name = ' '.join((request.POST.get('teacher_name') or '').split())
    if not teacher_name or len(teacher_name) > 100:
        return HttpResponseBadRequest('Enter a valid teacher name.')
    if CourseTeacher.objects.filter(
        course_id=course_id, block=report.block, teacher_name__iexact=teacher_name,
    ).exclude(id=report.id).exists():
        messages.info(request, f'{teacher_name} is already listed for {report.block}.')
    else:
        report.teacher_name = teacher_name
        report.save(update_fields=['teacher_name'])
        messages.success(request, f'Updated the teacher for {report.block}.')
    return redirect('course_page', course_id=course_id)
