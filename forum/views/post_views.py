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
from forum.services.post_services import (
    create_post_service,
    update_post_service,
    delete_post_service,
    get_post_detail_service
)

logger = logging.getLogger(__name__)

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            try:
                content_json = request.POST.get('content')
                content_data = json.loads(content_json) if content_json else {}
                
                # Create post using service
                result = create_post_service(request.user, {
                    'title': form.cleaned_data['title'],
                    'content': content_data,
                    'courses': [course.id for course in form.cleaned_data['courses']],
                    'is_anonymous': True if request.POST.get("is_anonymous") == 'on' else False
                })

                if 'error' in result:
                    messages.error(request, result['error'])
                    return redirect('create_post')

                return redirect('post_detail', post_id=result['id'])
            except Exception as e:
                messages.error(request, f"Error creating post: {str(e)}")
        else:
            messages.error(request, f"Form validation failed: {form.errors}")
    else:
        form = PostForm()

    context = {
        'form': form,
        'action': 'Create',
        'post': None,
        'post_content': json.dumps({"blocks": [{"type": "paragraph", "data": {"text": ""}}]}),
        'selected_courses_json': '[]'
    }
    return render(request, 'forum/post_form.html', context)

@login_required
def post_detail(request, post_id):
    # Get post details using service
    result = get_post_detail_service(post_id, user=request.user)
    
    if 'error' in result:
        messages.error(request, result['error'])
        return redirect('all_posts')
        
    # Update notifications
    if request.user.is_authenticated:
        Notification.objects.filter(
            recipient=request.user,
            post_id=post_id,
            is_read=False
        ).update(is_read=True)

    post = Post.objects.get(id=post_id)  # Get the actual post object
    post.views += 1
    post.save()

    # Prepare forms and additional context
    solution_form = SolutionForm()
    comment_form = CommentForm()
    
    has_solution = Solution.objects.filter(post_id=post_id, author=request.user).exists()
    is_following = FollowedPost.objects.filter(user=request.user, post_id=post_id).exists() if request.user.is_authenticated else False

    # Process solutions for template
    processed_solutions = []
    for solution in result['solutions']:
        solution['is_saved'] = SavedSolution.objects.filter(
            user=request.user, 
            solution_id=solution['id']
        ).exists() if request.user.is_authenticated else False
        processed_solutions.append(solution)

    

    context = {
        'post': post,  # Use actual post object for template helpers
        'solutions' : result['solutions_object'],
        'post_data': result,
        'content_json': json.dumps(result['content']),
        'processed_solutions_json': json.dumps(processed_solutions),
        'has_solution_from_user': has_solution,
        'solution_form': solution_form,
        'comment_form': comment_form,
        'is_following': is_following,
        'courses': result['courses'],
        'like_count': result.get('like_count', 0),
        'is_liked_by_user': result.get('is_liked', False),
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

        selected_courses = list(post.courses.values('id', 'name', 'code', 'category'))
        selected_courses_json = json.dumps(selected_courses)
    except Exception as e:
        print(e)
        post_content = json.dumps({
            "blocks": [{"type": "paragraph", "data": {"text": ""}}]
        })
        selected_courses_json = '[]'

    context = {
        'post': post,
        'action': 'Edit',
        'post_content': post_content,
        'selected_courses_json': selected_courses_json,
        'form': None  # Not needed for edit
    }

    # print(selected_courses_json)
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
        post = get_object_or_404(Post, id=post_id)
        like, created = PostLike.objects.get_or_create(user=request.user, post=post)
        return JsonResponse({'success': True, 'liked': True, 'like_count': post.like_count()})
    return JsonResponse({'success': False}, status=400)

@login_required
def unlike_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        PostLike.objects.filter(user=request.user, post=post).delete()
        return JsonResponse({'success': True, 'liked': False, 'like_count': post.like_count()})
    return JsonResponse({'success': False}, status=400)