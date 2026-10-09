"""Actions for voting on polls, shared by the website and mobile API."""

from django.db import transaction

from forum.models import Poll, PollVote
from forum.services.post_services import _check_teacher_visibility, record_post_activity
from forum.services.results import service_error


def cast_poll_vote(user, poll_id, selected_option_ids):
    """Create or replace a user's vote after validating the selected options."""
    try:
        poll = Poll.objects.get(id=poll_id)
    except Poll.DoesNotExist:
        return service_error('Poll not found', 404)

    try:
        _check_teacher_visibility(user, poll)
    except ValueError as error:
        return service_error(error, 403)

    if not selected_option_ids:
        return service_error('No options selected')

    try:
        option_ids = [int(option_id) for option_id in selected_option_ids]
    except (TypeError, ValueError):
        return service_error('Invalid option selection')

    valid_option_ids = list(
        poll.options.filter(id__in=option_ids).values_list('id', flat=True)
    )
    if len(valid_option_ids) != len(set(option_ids)):
        return service_error('One or more options do not belong to this poll')
    if not poll.allow_multiple_choice and len(valid_option_ids) > 1:
        return service_error('You may only select one option for this poll')

    with transaction.atomic():
        vote, created = PollVote.objects.get_or_create(poll=poll, user=user)
        vote.selected_options.set(valid_option_ids)
        if not created:
            vote.save(update_fields=['updated_at'])

        # A new fifth vote is meaningful feed activity. Editing an existing vote is not.
        if created and poll.votes.count() % 5 == 0:
            record_post_activity(poll)

    return {'poll': poll, 'message': 'Vote recorded successfully'}


def remove_poll_vote(user, poll_id):
    """Remove the current user's vote from a poll."""
    try:
        poll = Poll.objects.get(id=poll_id)
    except Poll.DoesNotExist:
        return service_error('Poll not found', 404)

    try:
        _check_teacher_visibility(user, poll)
    except ValueError as error:
        return service_error(error, 403)

    deleted_count, _ = PollVote.objects.filter(poll=poll, user=user).delete()
    if not deleted_count:
        return service_error('No vote found to remove', 404)

    return {'poll': poll, 'message': 'Vote removed successfully'}
