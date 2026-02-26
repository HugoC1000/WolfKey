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
    create_post,
    like_post,
    unlike_post,
    follow_post,
    unfollow_post
)

from forum.views.feed_views import (
    all_posts,
    for_you,
    my_posts
)
from forum.views.solution_views import (
    create_solution,
    delete_solution,
    edit_solution,
    upvote_solution, 
    downvote_solution,
    accept_solution,
    get_sorted_solutions,
    
)
from forum.views.search_views import search_results_new_page
from forum.views.profile_views import (
    add_experience,
    remove_experience,
    add_help_request,
    remove_help_request,
    my_profile,
    profile_view,
    update_courses,
    upload_profile_picture
)
from forum.services.course_services import (
    course_search
)
from forum.views.save_views import (
    followed_posts,
    save_solution,
    saved_solutions,
)
from forum.views.notification_views import (
    all_notifications,
    mark_notification_read,
    mark_all_notifications_read
)
from forum.views.updates_views import acknowledge_update
from forum.services.utils import upload_image

from forum.views.comments_views import (
    create_comment,
    edit_comment,
    delete_comment,
    get_comments
)
from forum.views.course_comparer_views import (
    course_comparer
)
from forum.views.timetable_assigner_views import (
    timetable_assigner
)
from forum.views.timetable_assigner_views import (
    all_courses_blocks_view,
    generate_schedules_view,
)
from forum.api.schedule import(
    get_daily_schedule,
    get_user_blocks_api,
    check_ceremonial_uniform,
    process_schedule_api,
)
from forum.views.schedule_views import (
    daily_schedule_view,
    user_blocks_view,
)
from forum.api.auth import(
    api_login,
    api_register,
    api_upload_image,
    search_users_api,
    api_refresh_token,
    api_verify_token,
    api_logout,
    api_delete_account
)
from forum.views.auth_views import register, login_view, logout_view


from django.views.generic import RedirectView

from forum.api.timetable import (
    evaluate_timetable_api,
    generate_schedules_api,
    all_courses_blocks_api
)

from forum.views.about_view import about_view
from forum.views.privacy_view import privacy_view
from forum.views.volunteer_views import volunteer_hours_page
from forum.views.volunteer_admin_views import (
    volunteer_admin_page,
    create_milestone,
    update_milestone,
    delete_milestone,
    create_resource,
    update_resource,
    delete_resource,
)

from forum.api.debug import debug_logs

from forum.api.volunteer import (
    volunteer_hours_api,
    volunteer_milestones_api,
    volunteer_resources_api,
)

from forum.api.notifications import (
    notifications_api,
    mark_notification_read_api,
    mark_all_notifications_read_api,
    register_push_token_api,
    unregister_push_token_api,
    unread_count_api,
    mark_notifications_by_post_api
)

from forum.api.posts import (
    post_detail_api,
    create_post_api,
    update_post_api,
    delete_post_api,
    like_post_api,
    unlike_post_api,
    follow_post_api,
    unfollow_post_api,
    get_post_share_info_api,
    for_you_api, all_posts_api
)

from forum.api.solutions import (
    create_solution_api,
    update_solution_api,
    delete_solution_api,
    vote_solution_api,
    accept_solution_api
)

from forum.api.comment import (
    create_comment_api,
    edit_comment_api,
    delete_comment_api,
    get_comments_api
)

from forum.api.profile import (
    get_profile_api,
    update_profile_api,
    upload_profile_picture_api,
    upload_lunch_card_api,
    delete_lunch_card_api,
    update_courses_api,
    add_experience_api,
    add_help_request_api,
    remove_experience_api,
    remove_help_request_api,
    update_privacy_preferences_api,
)

urlpatterns = [

    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'forum/images/WolfkeyLogo.ico')),
    # Post related URLs
    path('', for_you, name='for_you'),
    path('all-posts/', all_posts, name='all_posts'),
    path('post/<int:post_id>/', post_detail, name='post_detail'),
    path('post/<int:post_id>/edit/', edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', delete_post, name='delete_post'),
    path('post/create/', create_post, name='create_post'),
    path('posts/<int:post_id>/like/', like_post, name='like_post'),
    path('posts/<int:post_id>/unlike/', unlike_post, name='unlike_post'),

    path('solution/<int:solution_id>/edit/', edit_solution, name='edit_solution'),
    path('solution/<int:solution_id>/delete/', delete_solution, name='delete_solution'),
    path('solution/<int:post_id>/create/', create_solution, name='create_solution'),
    path('post/<int:post_id>/solutions/sorted/', get_sorted_solutions, name='get_sorted_solutions'),


    path('comment/create/<int:solution_id>/', create_comment, name='create_comment'),
    path('comment/edit/<int:comment_id>/', edit_comment, name='edit_comment'),
    path('comment/delete/<int:comment_id>/', delete_comment, name='delete_comment'),

    path('solution/<int:solution_id>/comments/', get_comments, name='get_solution_comments'),

    path('about', about_view, name = 'site_info'),
    path('privacy', privacy_view, name = 'privacy_policy'),
    path('service/', volunteer_hours_page, name='volunteer_hours'),
    path('service/admin/', volunteer_admin_page, name='volunteer_admin'),
    path('service/admin/milestone/create/', create_milestone, name='create_milestone'),
    path('service/admin/milestone/<int:milestone_id>/update/', update_milestone, name='update_milestone'),
    path('service/admin/milestone/<int:milestone_id>/delete/', delete_milestone, name='delete_milestone'),
    path('service/admin/resource/create/', create_resource, name='create_resource'),
    path('service/admin/resource/<int:resource_id>/update/', update_resource, name='update_resource'),
    path('service/admin/resource/<int:resource_id>/delete/', delete_resource, name='delete_resource'),
    
    # Volunteer Hours API endpoints
    path('api/volunteer/hours/', volunteer_hours_api, name='api_volunteer_hours'),
    path('api/volunteer/milestones/', volunteer_milestones_api, name='api_volunteer_milestones'),
    path('api/volunteer/resources/', volunteer_resources_api, name='api_volunteer_resources'),
    
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
    path('profile/upload-picture/', upload_profile_picture, name='upload_profile_picture'),
    path('my-profile/', my_profile, name='my_profile'),
    path('profile/<str:username>/', profile_view, name='profile'),
    path('update-courses/', update_courses, name='update_courses'),
    
    # Course management URLs
    path('courses/experience/add/', add_experience, name='add_experience'),
    path('courses/experience/remove/<int:experience_id>/', remove_experience, name='remove_experience'),
    path('courses/help/add/', add_help_request, name='add_help_request'),
    path('courses/help/remove/<int:help_id>/', remove_help_request, name='remove_help_request'),
    path('api/courses/', course_search, name='course-search'),
    
    # Course comparer URLs
    path('match/', course_comparer, name='course_comparer'),
    path('atlas/', timetable_assigner, name='timetable_assigner'),
    path('api/search-users/', search_users_api, name='search_users_api'),

    # Saved posts URLs
    path('followed-posts/', followed_posts, name='followed_posts'),
    path('my-posts/', my_posts, name='my_posts'),
    path('follow-post/<int:post_id>/', follow_post, name='follow_post'),
    path('unfollow-post/<int:post_id>/', unfollow_post, name='unfollow_post'),
    path('save-solution/<int:solution_id>/', save_solution, name='save_solution'),
    path('saved-solutions/', saved_solutions, name='saved_solutions'),

    # API URLs
    path('api/acknowledge-update/', acknowledge_update, name='acknowledge_update'),
    
    # Notification URLs
    path('notifications/', all_notifications, name='all_notifications'),
    path('notifications/mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<int:notification_id>/read/', mark_notification_read, name='mark_notification_read'),
    
    # Admin URL
    path('admin/', admin.site.urls),

    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Timetable API
    path('api/timetable/generate/', generate_schedules_api, name='api_generate_schedules'),
    path('api/timetable/evaluate/', evaluate_timetable_api, name='api_evaluate_timetable'),
    path('api/courses/all-courses-by-block/', all_courses_blocks_api, name='api_all_courses_blocks'),
    # Session-backed endpoints for website
    path('timetable/generate/', generate_schedules_view, name='session_generate_schedules'),
    path('courses/all-courses-by-block/', all_courses_blocks_view, name='session_all_courses_blocks'),
    
    # Authentication API endpoints
    path('api/auth/login/', api_login, name='api_login'),
    path('api/auth/register/', api_register, name='api_register'),
    path('api/auth/logout/', api_logout, name='api_logout'),
    path('api/auth/refresh-token/', api_refresh_token, name='api_refresh_token'),
    path('api/auth/verify-token/', api_verify_token, name='api_verify_token'),
    path('api/auth/delete-account/', api_delete_account, name='api_delete_account'),
    path('api/upload-image/', api_upload_image, name='api_upload_image'),
    
    path('schedules/daily/<str:target_date>/', daily_schedule_view, name='daily_schedule_view'),
    path('user-blocks/<int:user_id>/', user_blocks_view, name='user_schedule_view'),
    path('api/schedules/daily/<str:target_date>/', get_daily_schedule, name='api_get_daily_schedule'),
    path('api/user-blocks/<int:user_id>/', get_user_blocks_api, name='api_get_user_schedule'),
    path('api/process-schedule/<int:user_id>/', process_schedule_api, name='api_process_schedule'),
    path('api/debug/logs/', debug_logs, name='api_debug_logs'),
    path('api/schedules/uniform/<str:target_date>/', check_ceremonial_uniform),

    path('api/for-you/', for_you_api, name='for_you_api'),
    path('api/posts/create/', create_post_api, name='api_create_post'),
    path('api/posts/<int:post_id>/', post_detail_api, name='api_post_detail'),
    path('api/posts/<int:post_id>/edit/', update_post_api, name='api_update_post'),
    path('api/posts/<int:post_id>/delete/', delete_post_api, name='api_delete_post'),
    
    # Post interaction API endpoints
    path('api/posts/<int:post_id>/like/', like_post_api, name='api_like_post'),
    path('api/posts/<int:post_id>/unlike/', unlike_post_api, name='api_unlike_post'),
    path('api/posts/<int:post_id>/follow/', follow_post_api, name='api_follow_post'),
    path('api/posts/<int:post_id>/unfollow/', unfollow_post_api, name='api_unfollow_post'),
    path('api/posts/<int:post_id>/share/', get_post_share_info_api, name='api_post_share_info'),
    
    # Solution API endpoints
    path('api/posts/<int:post_id>/solutions/create/', create_solution_api, name='api_create_solution'),
    path('api/solutions/<int:solution_id>/edit/', update_solution_api, name='api_update_solution'),
    path('api/solutions/<int:solution_id>/delete/', delete_solution_api, name='api_delete_solution'),
    path('api/solutions/<int:solution_id>/vote/', vote_solution_api, name='api_vote_solution'),
    path('api/solutions/<int:solution_id>/accept/', accept_solution_api, name='api_accept_solution'),
    path('api/all-posts/', all_posts_api, name='all_posts_api'),
    
    # Comment API endpoints
    path('api/solutions/<int:solution_id>/comments/create/', create_comment_api, name='api_create_comment'),
    path('api/comments/<int:comment_id>/edit/', edit_comment_api, name='api_edit_comment'),
    path('api/comments/<int:comment_id>/delete/', delete_comment_api, name='api_delete_comment'),
    path('api/solutions/<int:solution_id>/comments/', get_comments_api, name='api_get_comments'),
    
    # Notification API endpoints
    path('api/notifications/', notifications_api, name='api_notifications'),
    path('api/notifications/unread-count/', unread_count_api, name='api_notifications_unread_count'),
    path('api/notifications/<int:notification_id>/mark-read/', mark_notification_read_api, name='api_mark_notification_read'),
    path('api/notifications/mark-all-read/', mark_all_notifications_read_api, name='api_mark_all_notifications_read'),
    path('api/notifications/mark-by-post/<int:post_id>/', mark_notifications_by_post_api, name='api_mark_notifications_by_post'),
    path('api/notifications/register-push-token/', register_push_token_api, name='api_register_push_token'),
    path('api/notifications/unregister-push-token/', unregister_push_token_api, name='api_unregister_push_token'),
    
    # Profile API endpoints
    path('api/profile/', get_profile_api, name='api_get_current_profile'),
    path('api/profile/update/', update_profile_api, name='api_update_profile'),
    path('api/profile/upload-picture/', upload_profile_picture_api, name='api_upload_profile_picture'),
    path('api/profile/upload-lunch-card/', upload_lunch_card_api, name='api_upload_lunch_card'),
    path('api/profile/delete-lunch-card/', delete_lunch_card_api, name='api_delete_lunch_card'),
    path('api/profile/courses/update/', update_courses_api, name='api_update_courses'),
    path('api/profile/preferences/update/', update_privacy_preferences_api, name='api_update_privacy_preferences'),
    path('api/profile/<str:username>/', get_profile_api, name='api_get_profile'),
    path('api/profile/experience/add/', add_experience_api, name='api_add_experience'),
    path('api/profile/help/add/', add_help_request_api, name='api_add_help_request'),
    path('api/profile/experience/<int:experience_id>/remove/', remove_experience_api, name='api_remove_experience'),
    path('api/profile/help/<int:help_id>/remove/', remove_help_request_api, name='api_remove_help_request'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)