from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from forum.models import Post, SavedPost, FollowedPost, Solution, SavedSolution
from forum.services.utils import process_post_preview, add_course_context, annotate_post_card_context
from forum.services.solution_services import save_solution_service
from forum.serializers import PostListSerializer, SolutionSerializer, attach_poll_data_to_posts
import json

@login_required
def followed_posts(request):
    posts_queryset = Post.objects.filter(followers__user=request.user)
    
    if request.user.is_authenticated and request.user.is_teacher:
        posts_queryset = posts_queryset.filter(allow_teacher=True)
    
    posts_queryset = annotate_post_card_context(posts_queryset, request.user)
    posts = list(posts_queryset)
    posts_data = PostListSerializer(posts, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts, posts_data)

    return render(request, 'forum/followed_posts.html', {
        'posts': posts,
        'posts_data': posts_data
    })

@login_required
def save_solution(request, solution_id):
    if request.method == 'POST':
        result = save_solution_service(request.user, solution_id)
        
        if 'error' in result:
            return JsonResponse({
                'success': False,
                'message': result['error'],
                'messages': result.get('messages', [])
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'saved': result['saved'],
            'messages': result.get('messages', [])
        })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method',
        'messages': [{'message': 'Invalid request method', 'tags': 'error'}]
    }, status=400)

@login_required
def saved_solutions(request):
    solutions_queryset = Solution.objects.filter(saves__user=request.user).select_related('author', 'post')
    solutions = list(solutions_queryset)

    posts_for_cards = [solution.post for solution in solutions]
    posts_data = PostListSerializer(posts_for_cards, many=True, context={'request': request}).data
    attach_poll_data_to_posts(posts_for_cards, posts_data)
    
    # Serialize solutions for consistent structure with API
    solutions_data = []
    for solution in solutions:
        # Add post to context for proper serialization
        serializer = SolutionSerializer(solution, context={'request': request, 'post': solution.post})
        solutions_data.append(serializer.data)

    return render(request, 'forum/saved_solutions.html', {
        'solutions': solutions,  # Keep for template compatibility
        'solutions_data': solutions_data   # Serialized data
    })
