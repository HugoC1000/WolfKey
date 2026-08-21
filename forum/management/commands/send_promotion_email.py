import re

from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from forum.models import User


PREVIEW_EMAIL = 'chunghugo99994@gmail.com'
DEFAULT_NEWSLETTER = 'Announcement_New_Features'
SUBJECTS = {
    'Announcement_New_Features': "What's New: Profiles, Polls & Volunteer Hours",
    'atlas_intro': 'Find a Better Fit with Atlas',
    'atlas_schedule_upload': 'Upload Your Schedule to Atlas',
}


class Command(BaseCommand):
    help = 'Send a newsletter to all users or a single preview recipient'

    def add_arguments(self, parser):
        parser.add_argument(
            '--newsletter',
            default=DEFAULT_NEWSLETTER,
            help=(
                'Newsletter template name without .html, for example '
                'atlas_intro or atlas_schedule_upload.'
            ),
        )
        parser.add_argument(
            '--subject',
            help='Override the default subject for the selected newsletter.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help=f'Send only to the preview address {PREVIEW_EMAIL}; never contact the user list.',
        )

    def handle(self, *args, **kwargs):
        newsletter = kwargs['newsletter'].strip()
        if newsletter.endswith('.html'):
            newsletter = newsletter[:-5]
        if not re.fullmatch(r'[A-Za-z0-9_-]+', newsletter):
            self.stderr.write(self.style.ERROR('Newsletter must be a simple template name, without a path.'))
            return

        template_name = f'forum/newsletters/{newsletter}.html'
        subject = kwargs.get('subject') or SUBJECTS.get(newsletter, newsletter.replace('_', ' ').title())
        html_content = render_to_string(template_name)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@wolfkey.net')

        if kwargs['dry_run']:
            email = EmailMessage(subject, html_content, from_email, [PREVIEW_EMAIL])
            recipient_description = PREVIEW_EMAIL
        else:
            recipient_list_qs = (
                User.objects.values_list('personal_email', flat=True)
                .exclude(personal_email__isnull=True)
                .exclude(personal_email__exact='')
            )
            recipient_list = list(recipient_list_qs)
            to_address = getattr(settings, 'EMAIL_BCC_TO_ADDRESS', 'undisclosed-recipients@wolfkey.net')
            email = EmailMessage(subject, html_content, from_email, [to_address], bcc=recipient_list)
            recipient_description = f'{len(recipient_list)} users via BCC'

        email.content_subtype = "html"  # Set the email content type to HTML
        email.send()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent {newsletter} newsletter to {recipient_description}.'
            )
        )
