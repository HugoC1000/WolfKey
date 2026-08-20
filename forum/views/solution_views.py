# views/solution_views.py
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from ..services.utils import process_messages_to_json
from forum.forms import SolutionForm
from forum.models import Post, Solution
from forum.services.solution_services import (
    create_solution_service,
    update_solution_service,
    delete_solution_service,
    vote_solution_service,
    accept_solution_service,
    get_sorted_solutions_service
)
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json
from django.core import serializers
from forum.serializers import AnonymousAuthorSerializer, FeedUserSerializer

@login_required
def create_solution(request, post_id):
    if request.method == 'POST':
        solution_form = SolutionForm(request.POST)
        if solution_form.is_valid():
            try:
                solution_json = request.POST.get('content')
                solution_data = json.loads(solution_json) if solution_json else {}
                
                result = create_solution_service(request.user, post_id, {
                    'content': solution_data
                })
                
                if 'error' in result:
                    messages.error(request, result['error'])
                else:
                    messages.success(request, result['message'])
                
                return redirect('post_detail', post_id=post_id)
            except Exception as e:
                messages.error(request, str(e))
        
    messages.error(request, 'An error occurred.')
    return redirect('post_detail', post_id=post_id)

@login_required
def edit_solution(request, solution_id):
    solution = get_object_or_404(Solution, id=solution_id, author=request.user)

    if request.method == 'POST':
        solution_form = SolutionForm(request.POST, instance=solution)
        if solution_form.is_valid():
            try:
                solution_json = request.POST.get('content')
                solution_data = json.loads(solution_json) if solution_json else {}

                result = update_solution_service(request.user, solution_id, {
                    'content': solution_data
                })

                if 'error' in result:
                    messages.error(request, result['error'])
                else:
                    messages.success(request, result['message'])
                    messages_data = process_messages_to_json(request)
                    return JsonResponse({'status': 'success','messages': messages_data}, status=200)
            except ValueError as e:
                print(e)
                messages.error(request,str(e))
                messages_data = process_messages_to_json(request)
                return JsonResponse({'status': 'error','messages': messages_data}, status=200)
    messages.error(request, "Invalid request.")
    
    messages_data = process_messages_to_json(request)
    return JsonResponse({'status' : 'error', 'messages': messages_data}, status=400)

@login_required
def delete_solution(request, solution_id):
    solution = get_object_or_404(Solution, id=solution_id, author=request.user)
    
    if request.method == 'POST':
        result = delete_solution_service(request.user, solution_id)

        if 'error' in result:
            messages.error(request, result['error'])
        else:
            messages.success(request, result['message'])
            messages_data = process_messages_to_json(request)

            return JsonResponse({'status': 'success','messages': messages_data}, status=200)

    messages_data = process_messages_to_json(request)
    return JsonResponse({'status': 'error','messages': messages_data}, status=400)


@login_required
def upvote_solution(request, solution_id):
    solution = get_object_or_404(Solution, id=solution_id)
    result = vote_solution_service(request.user, solution_id, 'upvote')

    if 'conflict' in result:
        # Return 409 Conflict for duplicate votes
        return JsonResponse({
            'success': False,
            'message': result['error'],
            'messages': result.get('messages', [])
        }, status=409)
    elif 'error' in result:
        return JsonResponse({
            'success': False,
            'message': result['error'],
            'messages': result.get('messages', [])
        }, status=400)

    return JsonResponse({
        'success': True,
        'upvotes': result['upvotes'],
        'downvotes': result['downvotes'],
        'vote_state': result['vote_state'],
        'messages': result.get('messages', [])
    })

@login_required
def downvote_solution(request, solution_id):
    solution = get_object_or_404(Solution, id=solution_id)
    result = vote_solution_service(request.user, solution_id, 'downvote')

    if 'conflict' in result:
        # Return 409 Conflict for duplicate votes
        return JsonResponse({
            'success': False,
            'message': result['error'],
            'messages': result.get('messages', [])
        }, status=409)
    elif 'error' in result:
        return JsonResponse({
            'success': False,
            'message': result['error'],
            'messages': result.get('messages', [])
        }, status=400)
    
    return JsonResponse({
        'success': True,
        'upvotes': result['upvotes'],
        'downvotes': result['downvotes'],
        'vote_state': result['vote_state'],
        'messages': result.get('messages', [])
    })

@login_required
@require_http_methods(["POST"])
def accept_solution(request, solution_id):
    try:
        result = accept_solution_service(request.user, solution_id)
        
        if 'error' in result:
            return JsonResponse({
                'success': False,
                'message': result['error'],
                'messages': result.get('messages', [])
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'is_accepted': result['is_accepted'],
            'previous_solution_id': result.get('previous_solution_id'),
            'messages': result.get('messages', [])
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data',
            'messages': [{'message': 'Invalid JSON data', 'tags': 'error'}]
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e),
            'messages': [{'message': f'Server error: {str(e)}', 'tags': 'error'}]
        }, status=500)

def get_sorted_solutions(request, post_id):
    sort_by = request.GET.get('sort', 'votes')
    result = get_sorted_solutions_service(post_id, sort_by)
    
    if 'error' in result:
        return JsonResponse({
            'success': False,
            'message': result['error'],
            'messages': result.get('messages', [])
        }, status=400)
    
    solutions_data = []
    for solution in result['solutions']:
        should_be_anonymous = (
            solution.post.is_anonymous
            and solution.author_id == solution.post.author_id
        )
        author_serializer = (
            AnonymousAuthorSerializer if should_be_anonymous else FeedUserSerializer
        )
        solution_dict = {
            'id': solution.id,
            'content': solution.content,
            'author': author_serializer(solution.author, context={'request': request}).data,
            'created_at': solution.created_at.isoformat(),
            'upvotes': solution.upvotes,
            'downvotes': solution.downvotes,
            'is_accepted': solution.post.accepted_solution_id == solution.id if solution.post.accepted_solution_id else False
        }
        solutions_data.append(solution_dict)
    
    return JsonResponse({
        'success': True,
        'solutions': solutions_data
    })
