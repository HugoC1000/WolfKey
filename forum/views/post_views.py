from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
import json
import logging
from django.utils.html import escape
from forum.models import Post, Solution, FollowedPost, SavedSolution, Notification, PostLike
from ..services.utils import selective_quote_replace, detect_bad_words
from forum.forms import SolutionForm, CommentForm, PostForm
from forum.serializers import PostDetailSerializer, serialize_poll_display_data
from forum.services.post_services import (
    create_post_service,
    update_post_service,
    delete_post_service,
    get_post_detail_service,
    like_post_service,
    unlike_post_service,
    follow_post_service,
    unfollow_post_service
)
from forum.services.notification_services import mark_notifications_by_post_service

logger = logging.getLogger(__name__)


def build_poll_response_data(poll, request=None):
    """
    Build a JSON-safe poll payload for frontend updates.
    """
    poll_data = serialize_poll_display_data(poll, request=request)
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
    # Get post object and increment views
    post = get_object_or_404(Post, id=post_id)
    post.views += 1
    post.save(update_fields=['views'])
    
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
    post = get_object_or_404(Post, id=post_id)

    if request.user != post.author:
        messages.error(request, "You don't have permission to edit this post.")
        return redirect('post_detail', post_id=post.id)
    
    if request.method == 'POST':
        try:
            # Get the content from the form
            content = request.POST.get('content')
            if content:
                content = json.loads(content)
            detect_bad_words(content)  # This will raise ValueError if bad words are detected
            # Update post
            post.content = content
            
            # Handle courses
            course_ids = request.POST.getlist('courses')
            if course_ids:
                post.courses.set(course_ids)
            
            post.title = request.POST.get('title', post.title)
            post.is_anonymous = True if request.POST.get("is_anonymous") == 'on' else False
            post.allow_teacher = True if request.user.is_teacher else (True if request.POST.get("allow_teacher") == 'on' else False)
            post.save()
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
    post = get_object_or_404(Post, id=post_id)
    
    if post.author != request.user:
        return HttpResponseForbidden("You cannot delete this post")
        
    if request.method == 'POST':
        post.delete()
        messages.success(request, 'Post deleted successfully!')
        return redirect('all_posts')
        
    return render(request, 'forum/delete_confirm.html', {'post': post})

@login_required
def like_post(request, post_id):
    if request.method == 'POST':
        result = like_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse({'success': False, 'error': result['error']}, status=400)
        return JsonResponse({
            'success': result['success'],
            'liked': result['liked'],
            'like_count': result['like_count']
        })
    return JsonResponse({'success': False}, status=400)

@login_required
def unlike_post(request, post_id):
    if request.method == 'POST':
        result = unlike_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse({'success': False, 'error': result['error']}, status=400)
        return JsonResponse({
            'success': result['success'],
            'liked': result['liked'],
            'like_count': result['like_count']
        })
    return JsonResponse({'success': False}, status=400)

@login_required
def follow_post(request, post_id):
    if request.method == 'POST':
        result = follow_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse({'success': False, 'error': result['error']}, status=400)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': result['success'],
                'followed': result['followed'],
                'followers_count': result['followers_count']
            })
        
        return redirect('post_detail', post_id=post_id)
    return JsonResponse({'success': False}, status=400)

@login_required
def unfollow_post(request, post_id):
    if request.method == 'POST':
        result = unfollow_post_service(request.user, post_id)
        if 'error' in result:
            return JsonResponse({'success': False, 'error': result['error']}, status=400)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': result['success'],
                'followed': result['followed'],
                'followers_count': result['followers_count']
            })
        
        return redirect('post_detail', post_id=post_id)

@login_required
def vote_on_poll(request, post_id):
    """
    View to vote on a poll
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        from forum.models import Poll, PollVote
        
        poll = Poll.objects.get(id=post_id)
        
        # Get selected option IDs from POST data
        content_type = request.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            data = json.loads(request.body)
            selected_option_ids = data.get('selected_option_ids', [])
        else:
            selected_option_ids = request.POST.getlist('selected_option_ids')
        
        if not selected_option_ids:
            error_msg = 'No options selected'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('post_detail', post_id=post_id)
        
        # Convert to integers
        selected_option_ids = [int(id) for id in selected_option_ids]
        try:
            selected_option_ids = [int(id) for id in selected_option_ids]
        except (TypeError, ValueError):
            error_msg = 'Invalid option selection'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('post_detail', post_id=post_id)

        # Ensure selected options belong to this poll
        valid_option_ids = list(
            poll.options.filter(id__in=selected_option_ids).values_list('id', flat=True)
        )
        if not valid_option_ids:
            error_msg = 'No valid options selected'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('post_detail', post_id=post_id)

        # Enforce single-choice constraint when multiple choice is not allowed
        if not getattr(poll, 'allow_multiple_choice', False) and len(valid_option_ids) > 1:
            error_msg = 'You may only select one option for this poll'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('post_detail', post_id=post_id)

        # Check if user already voted
        existing_vote = PollVote.objects.filter(poll=poll, user=request.user).first()
        if existing_vote:
            # Update existing vote
            existing_vote.selected_options.set(valid_option_ids)
        else:
            # Create new vote
            poll_vote = PollVote.objects.create(poll=poll, user=request.user)
            poll_vote.selected_options.set(valid_option_ids)
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Vote recorded successfully',
                **build_poll_response_data(poll, request=request)
            }, status=200)
        
        # Handle regular form submissions
        messages.success(request, 'Your vote has been recorded')
        return redirect('post_detail', post_id=post_id)
        
    except Poll.DoesNotExist:
        error_msg = 'Poll not found'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=404)
        messages.error(request, error_msg)
        return redirect('/')
    except ValueError as e:
        error_msg = f'Invalid option IDs: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('post_detail', post_id=post_id)
    except Exception as e:
        error_msg = f'Error recording vote: {str(e)}'
        logger.error(error_msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=500)
        messages.error(request, error_msg)
        return redirect('post_detail', post_id=post_id)


@login_required
def remove_poll_vote(request, post_id):
    """
    View to remove a vote from a poll
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        from forum.models import Poll, PollVote
        
        poll = Poll.objects.get(id=post_id)
        poll_vote = PollVote.objects.filter(poll=poll, user=request.user).first()
        
        if not poll_vote:
            error_msg = 'No vote found to remove'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=404)
            messages.error(request, error_msg)
            return redirect('post_detail', post_id=post_id)
        
        poll_vote.delete()
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Vote removed successfully',
                **build_poll_response_data(poll, request=request)
            }, status=200)
        
        # Handle regular form submissions
        messages.success(request, 'Your vote has been removed')
        return redirect('post_detail', post_id=post_id)
        
    except Poll.DoesNotExist:
        error_msg = 'Poll not found'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=404)
        messages.error(request, error_msg)
        return redirect('/')
    except Exception as e:
        error_msg = f'Error removing vote: {str(e)}'
        logger.error(error_msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_msg}, status=500)
        messages.error(request, error_msg)
        return redirect('post_detail', post_id=post_id)
    return JsonResponse({'success': False}, status=400)