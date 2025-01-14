from django.urls import path
from . import views
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.home, name='home'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('post/create/', views.create_post, name='create_post'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('tag/create/', views.create_tag, name='create_tag'),
    path('solution/<int:solution_id>/upvote/', views.upvote_solution, name='upvote_solution'),
    path('solution/<int:solution_id>/downvote/', views.downvote_solution, name='downvote_solution'),
    path('comment/<int:comment_id>/upvote/', views.upvote_comment, name='upvote_comment'),
    path('search/', views.search_posts, name='search_posts'),
    path('search-results/', views.search_results_new_page, name='search_results_new_page'),
    path('admin/', admin.site.urls),
    path('upload/', views.handle_upload, name='handle_file_upload'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/', views.my_profile, name='my_profile'),
    path('save-post/<int:post_id>/', views.save_post, name='save_post'),
    path('unsave-post/<int:post_id>/', views.unsave_post, name='unsave_post'),
    path('saved_posts', views.saved_posts, name = "saved_posts"),
    path('myposts/', views.my_posts, name = 'my_posts'),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
