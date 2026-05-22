from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from forum.models import User

class Command(BaseCommand):
    help = 'Send promotion emails to all users'

    def handle(self, *args, **kwargs):
        # Get the recipient list
        recipient_list_qs = User.objects.values_list('personal_email', flat=True).exclude(personal_email__isnull=True).exclude(personal_email__exact='')
        recipient_list = list(recipient_list_qs)
        
        # Render the email content (use the new announcement newsletter)
        subject = "What's New: Profiles, Polls & Volunteer Hours"
        html_content = render_to_string('forum/newsletters/Announcement_New_Features.html')  # Path to new email template
        
        # Send the email
        # Put all recipients in BCC and use a single harmless To address to preserve privacy
        to_address = getattr(settings, 'EMAIL_BCC_TO_ADDRESS', 'undisclosed-recipients@wolfkey.net')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@wolfkey.net')
        email = EmailMessage(subject, html_content, from_email, [to_address], bcc=recipient_list)
        email.content_subtype = "html"  # Set the email content type to HTML
        email.send()

        self.stdout.write(self.style.SUCCESS(f'Successfully sent promotion email to {len(recipient_list)} users (via BCC).'))