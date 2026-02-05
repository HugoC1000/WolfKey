from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from forum.models import Notification
from forum.serializers import NotificationSerializer
from forum.services.notification_services import (
    send_course_notifications_service,
    send_solution_notification_service,
    send_comment_notifications_service,
    all_notifications_service,
    mark_notification_read_service,
)

@login_required
def all_notifications(request):
    from django.utils.html import strip_tags
    notifications_queryset = all_notifications_service(request.user)
    
    notifications_data = NotificationSerializer(
        notifications_queryset, 
        many=True, 
        context={'request': request}
    ).data
    
    for n in notifications_queryset:
        n.message = strip_tags(n.message)
    
    return render(request, 'forum/notifications.html', {
        'notifications': notifications_queryset,
        'notifications_data': notifications_data
    })

@login_required
def mark_notification_read(request, notification_id):
    notification = mark_notification_read_service(request.user, notification_id)
    if notification and notification.post:
        return redirect('post_detail', post_id=notification.post.id)
    return redirect('all_notifications')


@login_required
def mark_all_notifications_read(request):
    if request.method == 'POST':
        notifications = all_notifications_service(request.user)
        for n in notifications:
            if not n.is_read:
                mark_notification_read_service(request.user, n.id)
    return redirect('all_notifications')

def send_course_notifications(post, courses):
    send_course_notifications_service(post, courses)

def send_solution_notification(solution):
    send_solution_notification_service(solution)

def send_comment_notifications(comment, solution, parent_comment=None):
    send_comment_notifications_service(comment, solution, parent_comment)