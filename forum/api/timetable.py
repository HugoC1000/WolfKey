from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from forum.services.timetable_services import evaluate_multiple_schedules, generate_possible_schedules
from forum.models import Course, Block


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def all_courses_blocks_api(request):
    """Token-authenticated API endpoint to get all courses organized by their available blocks."""
    try:
        all_blocks = ['1A', '1B', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        blocks_data = {block_code: [] for block_code in all_blocks}

        # Determine grade threshold: use provided ?maxgrade= or user's profile grade if authenticated
        maxgrade_param = request.query_params.get('maxgrade', None)
        user_grade = None

        if maxgrade_param is not None:
            user_grade = int(maxgrade_param)
        elif request.user and request.user.is_authenticated:
            try:
                user_grade = int(request.user.userprofile.grade_level) if request.user.userprofile.grade_level is not None else None
            except Exception:
                user_grade = None

        courses_qs = Course.objects.prefetch_related('blocks').all()
        if user_grade is not None:
            from django.db.models import Q
            courses_qs = courses_qs.filter(Q(max_grade__isnull=True) | Q(max_grade__gte=user_grade))

        for course in courses_qs:
            for block in course.blocks.all():
                if block.code in blocks_data:
                    blocks_data[block.code].append(course.name)

        return Response({'success': True, 'blocks': blocks_data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def generate_schedules_api(request):
    """Token-authenticated API endpoint to generate possible schedules for given courses."""
    try:
        data = request.data
        requested_course_ids = data.get('requested_course_ids', [])
        if not requested_course_ids:
            return Response({'error': 'No courses requested'}, status=status.HTTP_400_BAD_REQUEST)

        required_course_ids = data.get('required_course_ids', [])
        schedules = generate_possible_schedules(requested_course_ids, required_course_ids=required_course_ids)
        return Response({'success': True, 'schedules': schedules}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def evaluate_timetable_api(request):
    """Token-authenticated API endpoint to evaluate timetable assignments."""
    try:
        data = request.data
        requested_course_ids = data.get('requested_course_ids', [])
        schedules = data.get('schedules', [])
        if not requested_course_ids:
            return Response({'error': 'No courses requested'}, status=status.HTTP_400_BAD_REQUEST)
        if not schedules:
            return Response({'error': 'No schedules provided'}, status=status.HTTP_400_BAD_REQUEST)

        results = evaluate_multiple_schedules(requested_course_ids, schedules)
        return Response({'success': True, 'results': results}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
