"""
URL configuration for student_forum project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path, include
from forum.views.auth_views import register, login_view, logout_view
from forum.views.auth_views import (
    CustomPasswordResetView,
    CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetCompleteView,
)
from forum.views.post_views import (
    post_detail, 
    edit_post, 
    delete_post, 
    create_post
)
from forum.views.search_views import (
    for_you, 
    all_posts,
    my_posts
)
from forum.views.solution_views import (
    create_solution,
    delete_solution,
    edit_solution,
    upvote_solution, 
    downvote_solution,
    accept_solution
)
from forum.views.search_views import search_results_new_page
from forum.views.profile_views import (
    add_experience,
    remove_experience,
    add_help_request,
    remove_help_request,
    edit_profile,
    my_profile,
    profile_view
)
from forum.views.course_views import (
    course_search
)
from forum.views.save_posts_views import (
    saved_posts,
    save_post,
    unsave_post,
)
from forum.views.notification_views import (
    all_notifications,
    mark_notification_read
)
from forum.views.updates_views import acknowledge_update
from forum.views.utils import upload_image

from forum.views.comments_views import (
    create_comment,
    edit_comment,
    delete_comment,
    get_comments
)

urlpatterns = [
    # Post related URLs
    path('', for_you, name='for_you'),
    path('all-posts/', all_posts, name='all_posts'),
    path('post/<int:post_id>/', post_detail, name='post_detail'),
    path('post/<int:post_id>/edit/', edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', delete_post, name='delete_post'),
    path('post/create/', create_post, name='create_post'),

    path('solution/<int:solution_id>/edit/', edit_solution, name='edit_solution'),
    path('solution/<int:solution_id>/delete/', delete_solution, name='delete_solution'),
    path('solution/<int:post_id>/create/', create_solution, name='create_solution'),

    path('comment/create/<int:solution_id>/', create_comment, name='create_comment'),
    path('comment/edit/<int:comment_id>/', edit_comment, name='edit_comment'),
    path('comment/delete/<int:comment_id>/', delete_comment, name='delete_comment'),

    path('solution/<int:solution_id>/comments/', get_comments, name='get_solution_comments'),
    
    # Auth related URLs
    path('register/', register, name='register'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # Voting URLs
    path('solution/<int:solution_id>/upvote/', upvote_solution, name='upvote_solution'),
    path('solution/<int:solution_id>/downvote/', downvote_solution, name='downvote_solution'),
    path('solution/<int:solution_id>/accept/', accept_solution, name='accept_solution'),
    
    # Search URLs
    path('search/', search_results_new_page, name='search_posts'),
    path('search-results/', search_results_new_page, name='search_results_new_page'),
    
    # Media upload URL
    path('upload-image/', upload_image, name='upload_image'),
    
    # Profile URLs
    path('profile/edit/', edit_profile, name='edit_profile'),
    path('my-profile/', my_profile, name='my_profile'),
    path('profile/<str:username>/', profile_view, name='profile'),
    
    # Course management URLs
    path('courses/experience/add/', add_experience, name='add_experience'),
    path('courses/experience/remove/<int:experience_id>/', remove_experience, name='remove_experience'),
    path('courses/help/add/', add_help_request, name='add_help_request'),
    path('courses/help/remove/<int:help_id>/', remove_help_request, name='remove_help_request'),
    path('api/courses/', course_search, name='course-search'),
    
    # Saved posts URLs
    path('saved-posts/', saved_posts, name='saved_posts'),
    path('my-posts/', my_posts, name='my_posts'),
    path('save-post/<int:post_id>/', save_post, name='save_post'),
    path('unsave-post/<int:post_id>/', unsave_post, name='unsave_post'),

    # API URLs
    path('api/acknowledge-update/', acknowledge_update, name='acknowledge_update'),
    
    # Notification URLs
    path('notifications/', all_notifications, name='all_notifications'),
    path('notifications/<int:notification_id>/read/', mark_notification_read, name='mark_notification_read'),
    
    # Admin URL
    path('admin/', admin.site.urls),

    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)