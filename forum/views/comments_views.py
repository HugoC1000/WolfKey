# views/comment_views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
import json

from forum.services.comment_services import (
    create_comment_service,
    edit_comment_service,
    delete_comment_service,
    get_comments_service,
    vote_comment_service,
)
from forum.serializers import AnonymousAuthorSerializer, FeedUserSerializer
from forum.views.json_responses import error_payload, success_payload


def _serialize_comments(comments, solution, request):
    def serialize_comment(comment):
        serializer_class = (
            AnonymousAuthorSerializer
            if solution.post.is_anonymous and comment.author_id == solution.post.author_id
            else FeedUserSerializer
        )
        return {
            'id': comment.id,
            'content': comment.content,
            'author': serializer_class(comment.author, context={'request': request}).data,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'replies': [serialize_comment(reply) for reply in comment.replies.all()],
        }

    return [serialize_comment(comment) for comment in comments]

@login_required
def create_comment(request, solution_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(error_payload('Invalid JSON data', error_code='invalid_json'), status=400)
        result = create_comment_service(request.user, solution_id, data)
        if 'error' not in result:
            return JsonResponse(success_payload({'id': result['id']}, result['message']), status=201)
        status_code = result.get('status', 400)
        return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    return JsonResponse(error_payload('Invalid request'), status=400)

@login_required
def edit_comment(request, comment_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(error_payload('Invalid JSON data', error_code='invalid_json'), status=400)
        result = edit_comment_service(request.user, comment_id, data)
        if 'error' not in result:
            return JsonResponse(success_payload({'id': result['id']}, result['message']))
        status_code = result.get('status', 400)
        return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    return JsonResponse(error_payload('Invalid request'), status=400)

@login_required
def delete_comment(request, comment_id):
    if request.method == 'POST':
        result = delete_comment_service(request.user, comment_id)
        if 'error' not in result:
            return JsonResponse(success_payload(None, result['message']))
        status_code = result.get('status', 400)
        return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    return JsonResponse(error_payload('Invalid request'), status=400)

def get_comments(request, solution_id):
    viewer = request.user if request.user.is_authenticated else None
    result = get_comments_service(viewer, solution_id)
    if 'error' in result:
        status_code = result.get('status', 400)
        return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('forum/components/comments_list.html', {
            'comments': result['comments'],
            'solution': result['solution'],
            'post': result['solution'].post,
        }, request=request)
        return JsonResponse(success_payload({
            'comments': _serialize_comments(result['comments'], result['solution'], request),
            'html': html,
        }))
    return render(request, 'forum/components/comments_list.html', {
        'comments': result['comments'],
        'solution': result['solution']
    })


@login_required
def vote_comment(request, comment_id, vote_type):
    if request.method != 'POST':
        return JsonResponse(error_payload('Invalid request'), status=400)
    result = vote_comment_service(request.user, comment_id, vote_type)
    if 'error' in result:
        status_code = result['status']
        return JsonResponse(error_payload(result['error'], status_code), status=status_code)
    return JsonResponse(success_payload({
        'upvotes': result['upvotes'],
        'downvotes': result['downvotes'],
        'vote_state': result['vote_state'],
    }, result['messages'][0]['message']))
