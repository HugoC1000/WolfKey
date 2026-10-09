from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from forum.services.feed_services import get_followed_posts

@login_required
def followed_posts(request):
    posts = get_followed_posts(request.user)

    return render(request, 'forum/followed_posts.html', {
        'posts': posts,
    })
