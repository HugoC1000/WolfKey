from forum.models import Solution, Comment, CommentUpvote, CommentDownvote
from django.db import transaction
from forum.services.notification_services import send_comment_notifications_service
from forum.services.mention_service import update_mentions
from forum.services.post_services import _check_teacher_visibility, record_post_activity
from forum.services.utils import detect_bad_words
from forum.services.results import service_error

def create_comment_service(user, solution_id, data):
    solution = Solution.objects.filter(id=solution_id).select_related('post').first()
    if solution is None:
        return service_error('Solution not found', 404)
    
    # Check teacher visibility on the post
    if user.is_authenticated:
        try:
            _check_teacher_visibility(user, solution.post)
        except ValueError as error:
            return service_error(error, 403)
    
    content = data.get('content')
    parent_id = data.get('parent_id')
    try:
        if isinstance(content, dict) and 'blocks' in content:
            blocks = content.get('blocks', [])
            if (len(blocks) == 1 and blocks[0].get('type') == 'paragraph' and not blocks[0].get('data', {}).get('text', '').strip()) or len(blocks) == 0:
                return service_error('Comment cannot be empty.')
        detect_bad_words(content)
    except Exception as e:
        return service_error(e)
    if content:
        parent_comment = None
        if parent_id:
            parent_comment = Comment.objects.filter(id=parent_id, solution=solution).first()
            if parent_comment is None:
                return service_error('Parent comment not found', 404)
        comment = Comment.objects.create(
            solution=solution,
            author=user,
            content=content,
            parent=parent_comment
        )

        record_post_activity(solution.post)
        
        # Update mentions in the comment content
        update_mentions(comment, content, old_content=None)
        
        send_comment_notifications_service(comment, solution, parent_comment)
        return {'id': comment.id, 'message': 'Comment created successfully'}
    return service_error('Invalid comment data.')

def edit_comment_service(user, comment_id, data):
    comment = Comment.objects.filter(id=comment_id, author=user).first()
    if comment is None:
        return service_error('Comment not found', 404)
    old_content = comment.content
    content = data.get('content')
    if content:
        try:
            detect_bad_words(content)
        except Exception as e:
            return service_error(e)
        comment.content = content
        comment.save()
        
        # Update mentions if content was updated
        update_mentions(comment, content, old_content=old_content)
        
        return {'id': comment.id, 'message': 'Comment edited successfully'}
    return service_error('Invalid comment data.')

def delete_comment_service(user, comment_id):
    comment = Comment.objects.filter(id=comment_id, author=user).first()
    if comment is None:
        return service_error('Comment not found', 404)
    comment.delete()
    return {'message': 'Comment deleted successfully'}

def get_comments_service(viewer, solution_id):
    solution = Solution.objects.filter(id=solution_id).select_related('post').first()
    if solution is None:
        return service_error('Solution not found', 404)
    try:
        _check_teacher_visibility(viewer, solution.post)
    except ValueError as error:
        return service_error(error, 403)

    comments = Comment.objects.filter(solution=solution).order_by('created_at')
    for comment in comments:
        comment.upvotes = comment.commentupvote_set.count()
        comment.downvotes = comment.commentdownvote_set.count()
        comment.vote_state = (
            'upvoted' if viewer and comment.commentupvote_set.filter(user=viewer).exists()
            else 'downvoted' if viewer and comment.commentdownvote_set.filter(user=viewer).exists()
            else 'none'
        )

    return {
        'comments': comments,
        'solution': solution
    }


def vote_comment_service(user, comment_id, vote_type):
    """Toggle one vote per user while keeping upvotes and downvotes exclusive."""
    if vote_type not in ('upvote', 'downvote'):
        return service_error('Invalid vote type')

    comment = Comment.objects.filter(id=comment_id).select_related('solution__post').first()
    if comment is None:
        return service_error('Comment not found', 404)
    try:
        _check_teacher_visibility(user, comment.solution.post)
    except ValueError as error:
        return service_error(error, 403)
    upvote, downvote = CommentUpvote, CommentDownvote
    selected, opposite = (upvote, downvote) if vote_type == 'upvote' else (downvote, upvote)
    with transaction.atomic():
        if opposite.objects.filter(comment=comment, user=user).delete()[0]:
            selected.objects.create(comment=comment, user=user)
            message = f'Comment {vote_type}d successfully'
        elif selected.objects.filter(comment=comment, user=user).delete()[0]:
            message = f'{vote_type.capitalize()} removed'
        else:
            selected.objects.create(comment=comment, user=user)
            message = f'Comment {vote_type}d successfully'
    return {
        'success': True,
        'upvotes': CommentUpvote.objects.filter(comment=comment).count(),
        'downvotes': CommentDownvote.objects.filter(comment=comment).count(),
        'vote_state': 'upvoted' if CommentUpvote.objects.filter(comment=comment, user=user).exists()
        else 'downvoted' if CommentDownvote.objects.filter(comment=comment, user=user).exists() else 'none',
        'messages': [{'message': message, 'tags': 'success'}],
    }
