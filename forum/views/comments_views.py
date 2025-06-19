# views/comment_views.py
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from forum.models import Post, Solution, Comment
from forum.forms import CommentForm
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from .notification_views import send_notification, send_comment_notifications
import json
from .utils import process_messages_to_json, detect_bad_words

from forum.services.comment_services import (
    create_comment_service,
    edit_comment_service,
    delete_comment_service,
    get_comments_service,
)

def create_comment(request, solution_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        result = create_comment_service(request, solution_id, data)
        if result['status'] == 'success':
            return JsonResponse({'status': 'success', 'messages': result['messages']}, status=201)
        else:
            return JsonResponse({'status': 'error', 'messages': result['messages']}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def edit_comment(request, comment_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        result = edit_comment_service(request, comment_id, data)
        if result['status'] == 'success':
            return JsonResponse({'status': 'success', 'messages': result['messages']}, status=200)
        else:
            return JsonResponse({'status': 'error', 'messages': result['messages']}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def delete_comment(request, comment_id):
    if request.method == 'POST':
        result = delete_comment_service(request, comment_id)
        if result['status'] == 'success':
            return JsonResponse({'status': 'success', 'messages': result['messages']}, status=200)
        else:
            return JsonResponse({'status': 'error', 'messages': result['messages']}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def get_comments(request, solution_id):
    result = get_comments_service(request, solution_id)
    print("REsult", result)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'comments': result['comments_data'],
            'html': result['html']
        })
    return render(request, 'forum/components/comments_list.html', {
        'comments': result['comments'],
        'solution': result['solution']
    })