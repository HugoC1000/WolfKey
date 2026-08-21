from django.core.management.base import BaseCommand
from django.db import transaction

from forum.models import UserCourseExperience, UserProfile
from forum.serializers.user import USER_SCHEDULE_BLOCKS


ALUMNI_GRADE_LEVEL = 13
ACTIVE_GRADE_LEVELS = range(8, ALUMNI_GRADE_LEVEL)


class Command(BaseCommand):
    help = (
        'Archive current schedule courses as experienced courses, clear schedules, '
        'and promote active students. Grade 13 alumni are not changed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report the changes without writing any data.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        schedule_fields = [f'block_{block}' for block in USER_SCHEDULE_BLOCKS]
        profiles = (
            UserProfile.objects
            .select_related('user')
            .filter(grade_level__in=ACTIVE_GRADE_LEVELS)
            .order_by('pk')
        )

        profiles_processed = 0
        assignments_archived = 0
        experience_records_created = 0

        with transaction.atomic():
            for profile in profiles.iterator():
                course_ids = {
                    getattr(profile, f'{field}_id')
                    for field in schedule_fields
                    if getattr(profile, f'{field}_id') is not None
                }
                assignments_archived += len(course_ids)

                existing_course_ids = set(
                    UserCourseExperience.objects.filter(
                        user_id=profile.user_id,
                        course_id__in=course_ids,
                    ).values_list('course_id', flat=True)
                )
                new_course_ids = course_ids - existing_course_ids
                experience_records_created += len(new_course_ids)

                if dry_run:
                    profiles_processed += 1
                    continue

                UserCourseExperience.objects.bulk_create([
                    UserCourseExperience(user_id=profile.user_id, course_id=course_id)
                    for course_id in new_course_ids
                ])

                for field in schedule_fields:
                    setattr(profile, field, None)
                profile.grade_level += 1
                profile.save(update_fields=[*schedule_fields, 'grade_level', 'updated_at'])
                profiles_processed += 1

            if dry_run:
                transaction.set_rollback(True)

        mode = 'Would promote' if dry_run else 'Promoted'
        self.stdout.write(self.style.SUCCESS(
            f'{mode} {profiles_processed} active students; '
            f'archived {assignments_archived} scheduled courses and '
            f'created {experience_records_created} experienced-course records. '
            f'Grade {ALUMNI_GRADE_LEVEL} alumni were not changed.'
        ))

