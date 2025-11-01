from django.shortcuts import get_object_or_404
from django.contrib import messages
from forum.models import Solution, Comment
from forum.services.notification_services import send_comment_notifications_service
from forum.services.utils import process_messages_to_json, detect_bad_words
from django.template.loader import render_to_string

def create_comment_service(request, solution_id, data):
    solution = get_object_or_404(Solution, id=solution_id)
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
            parent_comment = get_object_or_404(Comment, id=parent_id)
        comment = Comment.objects.create(
            solution=solution,
            author=request.user,
            content=content,
            parent=parent_comment
        )
        send_comment_notifications_service(comment, solution, parent_comment)
        messages.success(request, 'Comment created succesfully')
        return {'status': 'success', 'id': comment.id, 'messages': process_messages_to_json(request)}
    messages.error(request, 'Invalid comment data.')
    return {'status': 'error', 'messages': process_messages_to_json(request)}

def edit_comment_service(request, comment_id, data):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    content = data.get('content')
    if content:
        try:
            detect_bad_words(content)
        except Exception as e:
            messages.error(request, str(e))
            return {'status': 'error', 'messages': process_messages_to_json(request)}
        comment.content = content
        comment.save()
        messages.success(request, 'Solution edited succesfully')
        return {'status': 'success', 'messages': process_messages_to_json(request)}
    messages.error(request, 'Invalid comment data.')
    return {'status': 'error', 'messages': process_messages_to_json(request)}

def delete_comment_service(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    comment.delete()
    messages.success(request, 'Solution deleted succesfully')
    return {'status': 'success', 'messages': process_messages_to_json(request)}

def get_comments_service(request, solution_id):
    solution = get_object_or_404(Solution, id=solution_id)
    comments = Comment.objects.filter(solution=solution).order_by('created_at')

    def process_comment(comment):
        return {
            'id': comment.id,
            'content': comment.content,
            'author': {
                'name': comment.author.get_full_name(),
                'id': comment.author.id
            },
            'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'replies': [process_comment(reply) for reply in comment.replies.all()]
        }
    comments_data = [process_comment(comment) for comment in comments]

    html = render_to_string('forum/components/comments_list.html', {
        'comments': comments,
        'solution': solution
    }, request=request)
    return {
        'comments_data': comments_data,
        'html': html,
        'comments': comments,
        'solution': solution
    }
