# views/solution_views.py
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from forum.forms import SolutionForm
from forum.services.solution_services import (
    create_solution_service,
    update_solution_service,
    delete_solution_service,
    vote_solution_service,
    accept_solution_service,
    get_sorted_solutions_service,
    get_solution_for_author,
)
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json
from django.core import serializers
from forum.serializers import AnonymousAuthorSerializer, FeedUserSerializer
from forum.views.json_responses import error_payload, success_payload

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
    lookup = get_solution_for_author(request.user, solution_id)
    if 'error' in lookup:
        from django.http import Http404
        raise Http404(lookup['error'])
    solution = lookup['solution']

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
                    status_code = result.get('status', 400)
                    return JsonResponse(error_payload(result['error'], status_code), status=status_code)
                else:
                    return JsonResponse(success_payload({'id': result['id']}, result['message']))
            except ValueError as e:
                return JsonResponse(error_payload(str(e)), status=400)
    return JsonResponse(error_payload('Invalid request.'), status=400)

@login_required
def delete_solution(request, solution_id):
    if request.method == 'POST':
        result = delete_solution_service(request.user, solution_id)

        if 'error' in result:
            status_code = result.get('status', 400)
            return JsonResponse(error_payload(result['error'], status_code), status=status_code)
        else:
            return JsonResponse(success_payload(None, result['message']))

    return JsonResponse(error_payload('Invalid request.'), status=400)


@login_required
def upvote_solution(request, solution_id):
    result = vote_solution_service(request.user, solution_id, 'upvote')

    if 'error' in result:
        return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])

    return JsonResponse(success_payload({
        'upvotes': result['upvotes'],
        'downvotes': result['downvotes'],
        'vote_state': result['vote_state'],
    }, result['messages'][0]['message']))

@login_required
def downvote_solution(request, solution_id):
    result = vote_solution_service(request.user, solution_id, 'downvote')

    if 'error' in result:
        return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
    
    return JsonResponse(success_payload({
        'upvotes': result['upvotes'],
        'downvotes': result['downvotes'],
        'vote_state': result['vote_state'],
    }, result['messages'][0]['message']))

@login_required
@require_http_methods(["POST"])
def accept_solution(request, solution_id):
    try:
        result = accept_solution_service(request.user, solution_id)
        
        if 'error' in result:
            return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])

        return JsonResponse(success_payload({
            'is_accepted': result['is_accepted'],
            'previous_solution_id': result.get('previous_solution_id'),
        }, result['message']))
        
    except json.JSONDecodeError:
        return JsonResponse(error_payload('Invalid JSON data', error_code='invalid_json'), status=400)
    except Exception as e:
        return JsonResponse(error_payload(str(e), 500), status=500)

def get_sorted_solutions(request, post_id):
    sort_by = request.GET.get('sort', 'votes')
    result = get_sorted_solutions_service(post_id, sort_by)
    
    if 'error' in result:
        return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
    
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
    
    return JsonResponse(success_payload({'solutions': solutions_data}))
