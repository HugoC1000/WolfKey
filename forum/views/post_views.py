from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
import json
import logging
from django.utils.html import escape
from forum.forms import SolutionForm, CommentForm, PostForm
from forum.serializers import PostDetailSerializer, serialize_poll_display_data
from forum.services.post_services import (
    create_post_service,
    update_post_service,
    delete_post_service,
    get_post_detail_service,
    get_post_for_author,
    like_post_service,
    unlike_post_service,
    follow_post_service,
    unfollow_post_service,
    toggle_community_post_pin_service,
)
from forum.services.notification_services import mark_notifications_by_post_service
from forum.services.poll_services import cast_poll_vote, remove_poll_vote as remove_poll_vote_service
from forum.views.json_responses import error_payload, success_payload

logger = logging.getLogger(__name__)


def build_poll_response_data(poll, request=None):
    """
    Build a JSON-safe poll payload for frontend updates.
    """
    poll_data = serialize_poll_display_data(poll, viewer=request.user)
    if poll_data is not None:
        return poll_data

    return {
        'poll_options': [],
        'poll_info': {
            'allow_multiple_choice': poll.allow_multiple_choice,
            'is_public_voting': poll.is_public_voting,
            'total_votes': poll.votes.count()
        },
        'user_vote': None
    }

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            try:
                content_json = request.POST.get('content')
                content_data = json.loads(content_json) if content_json else {}
                
                # Create post using service
                allow_teacher = True if request.user.is_teacher else (True if request.POST.get("allow_teacher") == 'on' else False)
                
                # Parse poll data if present
                poll_data_json = request.POST.get('poll_data')
                poll_data = None
                if poll_data_json:
                    try:
                        poll_data = json.loads(poll_data_json)
                    except (json.JSONDecodeError, TypeError):
                        poll_data = None
                
                data_to_create = {
                    'title': form.cleaned_data['title'],
                    'content': content_data,
                    'courses': [course.id for course in form.cleaned_data['courses']],
                    'is_anonymous': True if request.POST.get("is_anonymous") == 'on' else False,
                    'allow_teacher': allow_teacher,
                    'poll_data': poll_data
                }

                result = create_post_service(request.user, data_to_create)

                if 'error' in result:
                    messages.error(request, result['error'])
                    return redirect('create_post')

                return redirect('post_detail', post_id=result['id'])
            except Exception as e:
                logger.exception("Error creating post")
                messages.error(request, f"Error creating post: {str(e)}")
                return redirect('create_post')
        else:
            messages.error(request, f"Form validation failed: {form.errors}")
            return redirect('create_post')
    else:
        form = PostForm()

    # Check if this is a poll creation request
    is_poll = request.GET.get('type') == 'poll'

    context = {
        'form': form,
        'action': 'Create',
        'post': None,
        'post_content': json.dumps({"blocks": [{"type": "paragraph", "data": {"text": ""}}]}),
        'selected_courses_json': json.dumps([]),
        'is_poll': is_poll,
        'poll_data': json.dumps({"is_poll": True, "question": "", "answers": ["", ""], "duration": "24", "allowMultiple": False, "isPublicVoting": True}) if is_poll else json.dumps({"is_poll": False})
    }
    return render(request, 'forum/post_form.html', context)

@login_required
def post_detail(request, post_id):
    result = get_post_detail_service(request.user, post_id)
    if 'error' in result:
        from django.http import Http404
        raise Http404(result['error'])
    post = result['post']
    
    # Mark notifications as read using service
    if request.user.is_authenticated:
        mark_notifications_by_post_service(request.user, post_id)

    serializer = PostDetailSerializer(post, context={'request': request})
    post_data = serializer.data

    solution_form = SolutionForm()
    comment_form = CommentForm()

    solutions = post.solutions.select_related('author').all()
    processed_solutions = post_data['solutions']

    context = {
        'post': post,
        'post_data': post_data,
        'content_json': json.dumps(post_data['content']),
        'processed_solutions_json': json.dumps(processed_solutions),
        'solutions': solutions,
        'solution_form': solution_form,
        'comment_form': comment_form,
    }

    return render(request, 'forum/post_detail.html', context)

@login_required
def edit_post(request, post_id):
    lookup = get_post_for_author(request.user, post_id)
    if 'error' in lookup:
        if lookup['status'] == 404:
            from django.http import Http404
            raise Http404(lookup['error'])
        messages.error(request, "You don't have permission to edit this post.")
        return redirect('post_detail', post_id=post_id)
    post = lookup['post']
    
    if request.method == 'POST':
        try:
            # Get the content from the form
            content = request.POST.get('content')
            if content:
                content = json.loads(content)

            # Use service so mention diffing + mention notifications run on edits.
            update_data = {
                'content': content,
                'title': request.POST.get('title', post.title),
                'is_anonymous': True if request.POST.get("is_anonymous") == 'on' else False,
                'allow_teacher': True if request.user.is_teacher else (True if request.POST.get("allow_teacher") == 'on' else False),
                'courses': request.POST.getlist('courses')
            }
            result = update_post_service(request.user, post_id, update_data)

            if 'error' in result:
                messages.error(request, result['error'])
                return redirect('edit_post', post_id=post.id)

            messages.success(request, 'Post updated successfully!')
            return redirect('post_detail', post_id=post.id)
        except ValueError as e:
            # Catch bad word detection errors
            messages.error(request, f"Content contains inappropriate language: {str(e)}")
        except json.JSONDecodeError as e:
            messages.error(request, 'Invalid content format')
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            messages.error(request, 'Error updating post')
            logger.error(f"Error updating post: {e}")
        
        return redirect('edit_post', post_id=post.id)
    
    try:
        content = post.content
        if isinstance(content, str):
            content = json.loads(content)
            
        # Escape HTML in text content
        for block in content.get('blocks', []):
            if block.get('type') == 'paragraph':
                block['data']['text'] = escape(block['data']['text'])
        
        post_content = json.dumps(content)

        from forum.serializers import CourseSerializer
        selected_courses = CourseSerializer(
            post.courses.all(), 
            many=True, 
            context={'request': request}
        ).data
        selected_courses_json = json.dumps(selected_courses)
    except Exception as e:
        print(e)
        post_content = json.dumps({
            "blocks": [{"type": "paragraph", "data": {"text": ""}}]
        })
        selected_courses_json = json.dumps([])

    context = {
        'post': post,
        'action': 'Edit',
        'post_content': post_content,
        'selected_courses_json': selected_courses_json,
        'form': None
    }

    return render(request, 'forum/post_form.html', context)


@login_required
def delete_post(request, post_id):
    lookup = get_post_for_author(request.user, post_id)
    if 'error' in lookup:
        return HttpResponse(lookup['error'], status=lookup['status'])
    post = lookup['post']
        
    if request.method == 'POST':
        result = delete_post_service(request.user, post_id)
        if 'error' in result:
            return HttpResponse(result['error'], status=result['status'])
        messages.success(request, 'Post deleted successfully!')
        return redirect('all_posts')
        
    return render(request, 'forum/delete_confirm.html', {'post': post})


@login_required
def toggle_community_post_pin(request, post_id):
    if request.method != 'POST':
        return HttpResponseForbidden('POST required')
    result = toggle_community_post_pin_service(request.user, post_id)
    if 'error' in result:
        return HttpResponse(result['error'], status=result['status'])
    messages.success(request, 'Post pinned in Community.' if result['pinned'] else 'Post unpinned from Community.')
    return redirect('post_detail', post_id=post_id)

@login_required
def like_post(request, post_id):
    if request.method == 'POST':
        result = like_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
        return JsonResponse(success_payload({
            'liked': result['liked'],
            'like_count': result['like_count']
        }))
    return JsonResponse(error_payload('Invalid request method.'), status=405)

@login_required
def unlike_post(request, post_id):
    if request.method == 'POST':
        result = unlike_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
        return JsonResponse(success_payload({
            'liked': result['liked'],
            'like_count': result['like_count']
        }))
    return JsonResponse(error_payload('Invalid request method.'), status=405)

@login_required
def follow_post(request, post_id):
    if request.method == 'POST':
        result = follow_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(success_payload({
                'followed': result['followed'],
                'followers_count': result['followers_count']
            }))
        
        return redirect('post_detail', post_id=post_id)
    return JsonResponse(error_payload('Invalid request method.'), status=405)

@login_required
def unfollow_post(request, post_id):
    if request.method == 'POST':
        result = unfollow_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(success_payload({
                'followed': result['followed'],
                'followers_count': result['followers_count']
            }))
        
        return redirect('post_detail', post_id=post_id)
    return JsonResponse(error_payload('Invalid request method.'), status=405)

@login_required
def vote_on_poll(request, post_id):
    """
    View to vote on a poll
    """
    if request.method != 'POST':
        return JsonResponse(error_payload('Method not allowed'), status=405)
    
    try:
        content_type = request.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            data = json.loads(request.body)
            selected_option_ids = data.get('selected_option_ids', [])
        else:
            selected_option_ids = request.POST.getlist('selected_option_ids')

        result = cast_poll_vote(request.user, post_id, selected_option_ids)
        if 'error' in result:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
            messages.error(request, result['error'])
            if result['error'] == 'Poll not found':
                return redirect('/')
            return redirect('post_detail', post_id=post_id)

        poll = result['poll']
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(success_payload(build_poll_response_data(poll, request=request), result['message']))
        
        # Handle regular form submissions
        messages.success(request, 'Your vote has been recorded')
        return redirect('post_detail', post_id=post_id)
        
    except Exception as e:
        error_msg = f'Error recording vote: {str(e)}'
        logger.error(error_msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(error_payload(error_msg, 500), status=500)
        messages.error(request, error_msg)
        return redirect('post_detail', post_id=post_id)


@login_required
def remove_poll_vote(request, post_id):
    """
    View to remove a vote from a poll
    """
    if request.method != 'POST':
        return JsonResponse(error_payload('Method not allowed'), status=405)
    
    try:
        result = remove_poll_vote_service(request.user, post_id)
        if 'error' in result:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(error_payload(result['error'], result['status']), status=result['status'])
            messages.error(request, result['error'])
            if result['error'] == 'Poll not found':
                return redirect('/')
            return redirect('post_detail', post_id=post_id)

        poll = result['poll']
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(success_payload(build_poll_response_data(poll, request=request), result['message']))
        
        # Handle regular form submissions
        messages.success(request, 'Your vote has been removed')
        return redirect('post_detail', post_id=post_id)
        
    except Exception as e:
        error_msg = f'Error removing vote: {str(e)}'
        logger.error(error_msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(error_payload(error_msg, 500), status=500)
        messages.error(request, error_msg)
        return redirect('post_detail', post_id=post_id)
