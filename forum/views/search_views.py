import json
from django.shortcuts import render, redirect
from forum.services.search_services import search_posts, search_users
from forum.serializers import PostListSerializer, UserSerializer

def search_results_new_page(request):
    query = request.GET.get('q', '')
    if query:
        posts_queryset = search_posts(request.user, query)
        users_queryset = search_users(request.user, query)
        
        posts_data = PostListSerializer(posts_queryset, many=True, context={'request': request}).data
        users_data = UserSerializer(users_queryset, many=True, context={'request': request}).data
        
        context = {
            'posts': posts_queryset,
            'users': users_queryset,
            'posts_data': posts_data,
            'users_data': users_data,
            'query': query
        }
        
        if request.user.is_authenticated:
            context['can_compare'] = True
            current_user_data = {
                'id': request.user.id,
                'username': request.user.username,
                'full_name': request.user.get_full_name(),
                'school_email': getattr(request.user, 'school_email', ''),
                'profile_picture_url': request.user.userprofile.profile_picture.url if request.user.userprofile.profile_picture else None,
            }
            context['current_user_data'] = json.dumps(current_user_data)
        else:
            context['can_compare'] = False
        
        return render(request, 'forum/search_results.html', context)
    return redirect('all_posts')
