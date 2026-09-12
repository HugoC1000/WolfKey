# views/comment_views.py
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
import json

from forum.services.comment_services import (
    create_comment_service,
    edit_comment_service,
    delete_comment_service,
    get_comments_service,
    vote_comment_service,
)

@login_required
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
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'comments': result['comments_data'],
            'html': result['html']
        })
    return render(request, 'forum/components/comments_list.html', {
        'comments': result['comments'],
        'solution': result['solution']
    })


@login_required
def vote_comment(request, comment_id, vote_type):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    result = vote_comment_service(request.user, comment_id, vote_type)
    if 'error' in result:
        return JsonResponse(result, status=400)
    return JsonResponse(result)
