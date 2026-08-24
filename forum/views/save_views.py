from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from forum.models import Post
from forum.services.utils import annotate_post_card_context
from forum.serializers import PostListSerializer
from forum.services.poll_display_service import attach_poll_data_to_posts

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
