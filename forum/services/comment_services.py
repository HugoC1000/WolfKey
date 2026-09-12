from django.shortcuts import get_object_or_404
from django.contrib import messages
from forum.models import Solution, Comment, CommentUpvote, CommentDownvote
from django.db import transaction
from forum.services.notification_services import send_comment_notifications_service
from forum.services.mention_service import update_mentions
from forum.services.post_services import _check_teacher_visibility
from forum.services.utils import process_messages_to_json, detect_bad_words
from django.template.loader import render_to_string
from forum.serializers import AnonymousAuthorSerializer, FeedUserSerializer

def create_comment_service(request, solution_id, data):
    solution = get_object_or_404(Solution, id=solution_id)
    
    # Check teacher visibility on the post
    if request.user.is_authenticated:
        _check_teacher_visibility(request.user, solution.post)
    
    content = data.get('content')
    parent_id = data.get('parent_id')
    try:
        if isinstance(content, dict) and 'blocks' in content:
            blocks = content.get('blocks', [])
            if (len(blocks) == 1 and blocks[0].get('type') == 'paragraph' and not blocks[0].get('data', {}).get('text', '').strip()) or len(blocks) == 0:
                messages.error(request, 'Comment cannot be empty.')
                return {'status': 'error', 'messages': process_messages_to_json(request)}
        detect_bad_words(content)
    except Exception as e:
        messages.error(request, str(e))
        return {'status': 'error', 'messages': process_messages_to_json(request)}
    if content:
        parent_comment = None
        if parent_id:
            parent_comment = get_object_or_404(Comment, id=parent_id, solution=solution)
        comment = Comment.objects.create(
            solution=solution,
            author=request.user,
            content=content,
            parent=parent_comment
        )
        
        # Update mentions in the comment content
        update_mentions(comment, content, old_content=None)
        
        send_comment_notifications_service(comment, solution, parent_comment)
        messages.success(request, 'Comment created successfully')
        return {'status': 'success', 'id': comment.id, 'messages': process_messages_to_json(request)}
    messages.error(request, 'Invalid comment data.')
    return {'status': 'error', 'messages': process_messages_to_json(request)}

def edit_comment_service(request, comment_id, data):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    old_content = comment.content
    content = data.get('content')
    if content:
        try:
            detect_bad_words(content)
        except Exception as e:
            messages.error(request, str(e))
            return {'status': 'error', 'messages': process_messages_to_json(request)}
        comment.content = content
        comment.save()
        
        # Update mentions if content was updated
        update_mentions(comment, content, old_content=old_content)
        
        messages.success(request, 'Comment edited successfully')
        return {'status': 'success', 'messages': process_messages_to_json(request)}
    messages.error(request, 'Invalid comment data.')
    return {'status': 'error', 'messages': process_messages_to_json(request)}

def delete_comment_service(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    comment.delete()
    messages.success(request, 'Comment deleted successfully')
    return {'status': 'success', 'messages': process_messages_to_json(request)}

def get_comments_service(request, solution_id):
    solution = get_object_or_404(Solution, id=solution_id)
    comments = Comment.objects.filter(solution=solution).order_by('created_at')
    viewer = request.user if request.user.is_authenticated else None
    for comment in comments:
        comment.upvotes = comment.commentupvote_set.count()
        comment.downvotes = comment.commentdownvote_set.count()
        comment.vote_state = (
            'upvoted' if viewer and comment.commentupvote_set.filter(user=viewer).exists()
            else 'downvoted' if viewer and comment.commentdownvote_set.filter(user=viewer).exists()
            else 'none'
        )

    def process_comment(comment):
        should_be_anonymous = (
            solution.post.is_anonymous
            and comment.author_id == solution.post.author_id
        )
        author_serializer = (
            AnonymousAuthorSerializer if should_be_anonymous else FeedUserSerializer
        )
        return {
            'id': comment.id,
            'content': comment.content,
            'author': author_serializer(
                comment.author,
                context={'request': request},
            ).data,
            'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'replies': [process_comment(reply) for reply in comment.replies.all()]
        }
    comments_data = [process_comment(comment) for comment in comments]

    html = render_to_string('forum/components/comments_list.html', {
        'comments': comments,
        'solution': solution,
        'post': solution.post,
    }, request=request)
    return {
        'comments_data': comments_data,
        'html': html,
        'comments': comments,
        'solution': solution
    }


def vote_comment_service(user, comment_id, vote_type):
    """Toggle one vote per user while keeping upvotes and downvotes exclusive."""
    if vote_type not in ('upvote', 'downvote'):
        return {'error': 'Invalid vote type'}

    comment = get_object_or_404(Comment, id=comment_id)
    _check_teacher_visibility(user, comment.solution.post)
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
