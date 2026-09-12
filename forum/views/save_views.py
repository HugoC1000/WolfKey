from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from forum.models import Post
from forum.services.post_list_service import prepare_posts

@login_required
def followed_posts(request):
    posts_queryset = Post.objects.filter(followers__user=request.user)
    
    if request.user.is_authenticated and request.user.is_teacher:
        posts_queryset = posts_queryset.filter(allow_teacher=True)
    
    posts = prepare_posts(posts_queryset, request.user)

    return render(request, 'forum/followed_posts.html', {
        'posts': posts,
    })
