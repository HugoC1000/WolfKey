from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, queue='general', routing_key='general.email')
def send_email_notification(self, recipient_email, subject, message):
    """
    Args:
        recipient_email (str): Email address to send to
        subject (str): Email subject line
        message (str): HTML email content
    
    Returns:
        str: Success message or raises exception on failure
    """
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
            html_message=message
        )
        logger.info(f"Email sent successfully to {recipient_email}")
        return f"Email sent to {recipient_email}"
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        raise
