from django.shortcuts import get_object_or_404
from django.conf import settings
from forum.models import UserCourseExperience, Notification, Post, Solution
from forum.services.utils import process_post_preview
import logging

logger = logging.getLogger(__name__)

def send_course_notifications_service(post, courses):
    experienced_users = UserCourseExperience.objects.filter(
        course__in=courses
    ).select_related('user').distinct('user')
    experienced_users = experienced_users.exclude(user=post.author)
    for exp_user in experienced_users:
        recipient = exp_user.user
        message = process_post_preview(post)
        url = post.get_absolute_url()
        email_subject = f'New post in your experienced course: {post.title}'
        email_message = f"""
        Hello {recipient.get_full_name()},
        
        A new post has been created in a course you have experience in:
        
        Title: {post.title}
        Course(s): {', '.join(c.name for c in courses)}
        
        You can view the post here:
        {settings.SITE_URL}{url}
        
        Best regards,
        WolfKey Team
        """
        send_notification_service(
            recipient=recipient,
            sender=post.get_author(),
            notification_type='post',
            message=message,
            url=url,
            post=post,
            email_subject=email_subject,
            email_message=email_message,
        )

def send_solution_notification_service(solution):
    post = solution.post
    author = post.author
    message = f'New solution to your question: {post.title}'
    url = post.get_absolute_url()
    email_subject = f'New solution to your question: {post.title}'
    email_message = f"""
    Hello {author.get_full_name()},
    
    A new solution has been posted to your question:
    
    Post: {post.title}
    Solution by: {solution.author.get_full_name()}
    
    You can view the solution here:
    {settings.SITE_URL}{url}
    
    Best regards,
    WolfKey Team
    """
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
        solution_author_email_message = f"""
        Hello {solution.author.get_full_name()},
        
        You can view the solution and comment here:
        {settings.SITE_URL}{solution.get_absolute_url()}
        
        Best regards,
        WolfKey Team
        """
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
        parent_author_email_message = f"""
        Hello {parent_comment.author.get_full_name()},
        
        {comment.author.get_full_name()} has replied to your comment:
  
        You can view the reply here:
        {settings.SITE_URL}{comment.get_absolute_url()}
        
        Best regards,
        WolfKey Team
        """
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
