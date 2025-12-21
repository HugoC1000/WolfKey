from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db.models import Q
from forum.models import UserCourseExperience, UserProfile, Notification, Post, Solution
from forum.services.utils import process_post_preview
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_email_template(template_name: str) -> str:
    """Load an email template from the email_templates folder next to this file."""
    base = Path(__file__).resolve().parent
    tpl_path = base / 'email_templates' / template_name
    try:
        return tpl_path.read_text(encoding='utf-8')
    except Exception:
        logger.exception(f"Failed to load email template: {template_name}")
        return ""


def _render_email(template_name: str, **context) -> str:
    tpl = _load_email_template(template_name)
    try:
        return tpl.format(**context)
    except Exception:
        logger.exception(f"Failed to render email template: {template_name}")
        return tpl

def send_course_notifications_service(post, courses):
    """
    Send notifications to users who:
    1. Have experience in the course (UserCourseExperience)
    2. Currently have the course in their schedule (any block)
    """
    notified_users = set()
    
    # Get users with experience in these courses
    experienced_users = UserCourseExperience.objects.filter(
        course__in=courses
    ).select_related('user').distinct('user')
    experienced_users = experienced_users.exclude(user=post.author)
    
    # Get users who currently have these courses in their schedule
    schedule_query = Q()
    for course in courses:
        schedule_query |= (
            Q(block_1A=course) | Q(block_1B=course) | Q(block_1D=course) | Q(block_1E=course) |
            Q(block_2A=course) | Q(block_2B=course) | Q(block_2C=course) | Q(block_2D=course) | Q(block_2E=course)
        )
    
    current_students = UserProfile.objects.filter(
        schedule_query
    ).select_related('user').exclude(user=post.author)
    
    # Send notifications to users with experience
    for exp_user in experienced_users:
        recipient = exp_user.user
        notified_users.add(recipient.id)
        message = process_post_preview(post)
        url = post.get_absolute_url()
        email_subject = f'New post in your experienced course: {post.title}'
        email_message = _render_email(
            'course_experienced.txt',
            recipient_full_name=recipient.get_full_name(),
            post_title=post.title,
            courses=', '.join(c.name for c in courses),
            site_url=settings.SITE_URL,
            post_url=url,
        )
        send_notification_service(
            recipient=recipient,
            sender=post.author,
            notification_type='post',
            message=message,
            url=url,
            post=post,
            email_subject=email_subject,
            email_message=email_message,
        )
    
    # Send notifications to current students (if not already notified)
    for profile in current_students:
        recipient = profile.user
        if recipient.id not in notified_users:
            notified_users.add(recipient.id)
            message = process_post_preview(post)
            url = post.get_absolute_url()
            email_subject = f'New post in your course: {post.title}'
            email_message = _render_email(
                'course_current.txt',
                recipient_full_name=recipient.get_full_name(),
                post_title=post.title,
                courses=', '.join(c.name for c in courses),
                site_url=settings.SITE_URL,
                post_url=url,
            )
            send_notification_service(
                recipient=recipient,
                sender=post.author,
                notification_type='post',
                message=message,
                url=url,
                post=post,
                email_subject=email_subject,
                email_message=email_message,
            )
    
    logger.info(f"Sent notifications for post {post.id} to {len(notified_users)} users (experienced + current students)")

def send_solution_notification_service(solution):
    post = solution.post
    author = post.author
    message = f'New solution to your question: {post.title}'
    url = post.get_absolute_url()
    email_subject = f'New solution to your question: {post.title}'
    email_message = _render_email(
        'solution.txt',
        author_full_name=author.get_full_name(),
        post_title=post.title,
        solution_author=solution.author.get_full_name(),
        site_url=settings.SITE_URL,
        post_url=url,
    )
    print("eter")
    send_notification_service(
        recipient=author,
        sender=solution.author,
        notification_type='solution',
        message=message,
        url=url,
        post=post,
        solution=solution,
        email_subject=email_subject,
        email_message=email_message,
    )

def send_comment_notifications_service(comment, solution, parent_comment=None):
    notified_users = set()
    if solution.author != comment.author:
        solution_author_message = f"{comment.author.get_full_name()} commented on your solution."
        solution_author_email_subject = f"New comment on your solution for '{solution.post.title}'"
        solution_author_email_message = _render_email(
            'solution_comment.txt',
            solution_author_full_name=solution.author.get_full_name(),
            site_url=settings.SITE_URL,
            solution_url=solution.get_absolute_url(),
        )
        send_notification_service(
            recipient=solution.author,
            sender=comment.author,
            notification_type='comment',
            message=solution_author_message,
            url=solution.get_absolute_url(),
            post=solution.post,
            solution=solution,
            email_subject=solution_author_email_subject,
            email_message=solution_author_email_message,
        )
        notified_users.add(solution.author)
    if parent_comment and parent_comment.author != comment.author and parent_comment.author not in notified_users:
        parent_author_message = f"{comment.author.get_full_name()} replied to your comment."
        parent_author_email_subject = f"New reply to your comment on '{solution.post.title}'"
        parent_author_email_message = _render_email(
            'reply.txt',
            parent_author_full_name=parent_comment.author.get_full_name(),
            comment_author_full_name=comment.author.get_full_name(),
            site_url=settings.SITE_URL,
            comment_url=comment.get_absolute_url(),
        )
        send_notification_service(
            recipient=parent_comment.author,
            sender=comment.author,
            notification_type='reply',
            message=parent_author_message,
            url=comment.get_absolute_url(),
            post=solution.post,
            solution=solution,
            email_subject=parent_author_email_subject,
            email_message=parent_author_email_message,
        )
        notified_users.add(parent_comment.author)

def send_notification_service(
    recipient, sender, notification_type, message, url=None, post=None, solution=None, email_subject=None, email_message=None
):
    created_notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        post=post,
        solution=solution,
        message=message,
    )
    
    # Send email using the separate email task
    if email_subject and email_message:
        from forum.tasks import send_email_notification
        send_email_notification.delay(
            recipient.personal_email,
            email_subject,
            email_message
        )
    
    try:
        from forum.services.expo_push_service import send_push_notification_to_user
        from forum.services.deep_link_service import create_notification_deep_link
        
        # Create push notification title and body
        push_title = f"New {notification_type.title()}"
        if notification_type == 'post':
            push_title = post.title
        elif notification_type == 'solution':
            push_title = "New Solution for your question"
        elif notification_type == 'comment':
            push_title = "New Comment"
        elif notification_type == 'reply':
            push_title = "New Reply"
        elif notification_type == 'grade_update':
            push_title = "Grade Update"
            
        push_body = message[:100] + "..." if len(message) > 100 else message

        deep_link_data = create_notification_deep_link(
            notification_type=notification_type,
            post=post,
            solution=solution,
            post_id=post.id if post else None,
            solution_id=solution.id if solution else None,
            user=sender
        )
        
        push_data = {
            'notification_id': str(created_notification.id),
            'notification_type': notification_type,
            'post_id': str(post.id) if post else None,
            'solution_id': str(solution.id) if solution else None,
            **deep_link_data
        }
        
        send_push_notification_to_user(
            user=recipient,
            title=push_title,
            body=push_body,
            data=push_data
        )
        
    except Exception as e:
        logger.error(f"Failed to send push notification: {str(e)}")

def all_notifications_service(user):
    return user.notifications.all()

def mark_notification_read_service(user, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=user)
    notification.is_read = True
    notification.save()
    return notification

def mark_notifications_by_post_service(user, post_id):
    """
    Mark all notifications associated with a specific post as read for the user.
    
    Args:
        user: The user whose notifications should be marked as read
        post_id: The ID of the post
    
    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the operation was successful
            - marked_count (int): Number of notifications marked as read
            - post_id (int): The post ID
            - error (str, optional): Error message if unsuccessful
    """
    try:
        # Verify the post exists
        post = get_object_or_404(Post, id=post_id)
        
        # Find all unread notifications for this user related to this post
        unread_notifications = Notification.objects.filter(
            recipient=user,
            post=post,
            is_read=False
        )
        
        marked_count = unread_notifications.count()
        
        # Mark them all as read
        unread_notifications.update(is_read=True)
        
        logger.info(f"Marked {marked_count} notifications as read for user {user.id} on post {post_id}")
        
        return {
            'success': True,
            'marked_count': marked_count,
            'post_id': post_id
        }
    except Post.DoesNotExist:
        return {
            'success': False,
            'error': 'Post not found'
        }
    except Exception as e:
        logger.error(f"Error marking notifications by post {post_id} for user {user.id}: {str(e)}")
        return {
            'success': False,
            'error': 'Failed to mark notifications as read'
        }
