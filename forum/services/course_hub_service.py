"""Class hub reads and teacher reports shared by website entry points."""

from collections import defaultdict

from django.db.models import Count
from django.db.models.functions import Coalesce

from forum.models import Course, CourseTeacher, Post, UserProfile
from forum.serializers.user import USER_SCHEDULE_BLOCKS
from forum.services.post_list_service import prepare_posts
from forum.services.results import service_error


def _has_uploaded_schedule(profile):
    return any(getattr(profile, f'block_{block}_id') for block in USER_SCHEDULE_BLOCKS)


def _can_access_course_hub(user):
    if user.is_staff:
        return True
    profile = getattr(user, 'userprofile', None)
    return bool(profile and profile.allow_schedule_comparison and _has_uploaded_schedule(profile))


def _can_manage_block_teacher(user, course, block):
    if user.is_staff:
        return True
    if block not in USER_SCHEDULE_BLOCKS or not _can_access_course_hub(user):
        return False
    return getattr(user.userprofile, f'block_{block}_id', None) == course.id


def get_course_hub(user, course_id):
    course = Course.objects.filter(id=course_id).prefetch_related('blocks').first()
    if course is None:
        return service_error('Course not found', 404)
    profile = user.userprofile
    result = {
        'course': course,
        'has_uploaded_schedule': _has_uploaded_schedule(profile),
        'allow_schedule_comparison': profile.allow_schedule_comparison,
        'access_granted': _can_access_course_hub(user),
    }
    if not result['access_granted']:
        return result

    blocks_by_code = {block.code: block for block in course.blocks.all()}
    course_blocks = [blocks_by_code[code] for code in USER_SCHEDULE_BLOCKS if code in blocks_by_code]
    student_profiles = UserProfile.objects.filter(
        allow_schedule_comparison=True, user__is_teacher=False,
    ).select_related('user')
    students_by_block = defaultdict(list)
    for block in course_blocks:
        students_by_block[block.code] = list(
            student_profiles.filter(**{f'block_{block.code}': course})
            .order_by('user__first_name', 'user__last_name')
        )
    reports_by_block = defaultdict(list)
    for report in CourseTeacher.objects.filter(course=course).order_by('block', 'teacher_name'):
        report.can_manage = _can_manage_block_teacher(user, course, report.block)
        reports_by_block[report.block].append(report)

    posts = Post.objects.filter(courses=course)
    if user.is_teacher:
        posts = posts.filter(allow_teacher=True)
    posts = posts.annotate(
        solution_count=Count('solutions', distinct=True),
        comment_count=Count('solutions__comments', distinct=True),
        total_response_count=Count('solutions', distinct=True) + Count('solutions__comments', distinct=True),
        recent_updated_at=Coalesce('last_activity_at', 'created_at'),
    ).select_related('author', 'author__userprofile').prefetch_related('courses').order_by(
        '-recent_updated_at', '-created_at',
    )
    result.update({
        'posts': prepare_posts(posts, user),
        'blocks': [
            {
                'code': block.code,
                'reports': reports_by_block[block.code],
                'can_contribute': _can_manage_block_teacher(user, course, block.code),
                'students': students_by_block[block.code],
            }
            for block in course_blocks
        ],
    })
    return result


def contribute_course_teacher(user, course_id, block, teacher_name):
    course = Course.objects.filter(id=course_id).first()
    if course is None:
        return service_error('Course not found', 404)
    block = (block or '').strip().upper()
    teacher_name = ' '.join((teacher_name or '').split())
    if not course.blocks.filter(code=block).exists() or not teacher_name or len(teacher_name) > 100:
        return service_error('Enter a valid block and teacher name.')
    if not _can_manage_block_teacher(user, course, block):
        return service_error('You must share this class to update its teacher information.', 403)
    if CourseTeacher.objects.filter(course=course, block=block, teacher_name__iexact=teacher_name).exists():
        return {'message': f'{teacher_name} is already listed for {block}.', 'duplicate': True}
    CourseTeacher.objects.create(course=course, block=block, teacher_name=teacher_name)
    return {'message': f'Added {teacher_name} for {block}.', 'duplicate': False}


def edit_course_teacher(user, course_id, report_id, teacher_name):
    report = CourseTeacher.objects.select_related('course').filter(id=report_id, course_id=course_id).first()
    if report is None:
        return service_error('Teacher report not found', 404)
    if not _can_manage_block_teacher(user, report.course, report.block):
        return service_error('You must share this class to update its teacher information.', 403)
    teacher_name = ' '.join((teacher_name or '').split())
    if not teacher_name or len(teacher_name) > 100:
        return service_error('Enter a valid teacher name.')
    if CourseTeacher.objects.filter(
        course_id=course_id, block=report.block, teacher_name__iexact=teacher_name,
    ).exclude(id=report.id).exists():
        return {'message': f'{teacher_name} is already listed for {report.block}.', 'duplicate': True}
    report.teacher_name = teacher_name
    report.save(update_fields=['teacher_name'])
    return {'message': f'Updated the teacher for {report.block}.', 'duplicate': False}
