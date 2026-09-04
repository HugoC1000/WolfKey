from django.core.management.base import BaseCommand, CommandError

from forum.models import User


class Command(BaseCommand):
    help = 'Create an active community account with a recovery email and temporary password.'

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True, help='Community name shown on WolfKey.')
        parser.add_argument('--email', required=True, help='Recovery email used for password resets.')
        parser.add_argument('--password', required=True, help='Temporary password to give the community.')
        parser.add_argument('--username', required=True, help='Short unique community handle.')

    def handle(self, *args, **options):
        username = options['username'].strip().lower()
        if User.objects.filter(username=username).exists():
            raise CommandError(f'Username "{username}" is already in use.')
        if User.objects.filter(personal_email__iexact=options['email']).exists():
            raise CommandError('That recovery email is already attached to an account.')
        name_parts = options['name'].strip().split(maxsplit=1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else 'Community'
        system_email = f'{username}@wpga.ca'
        if User.objects.filter(school_email=system_email).exists():
            raise CommandError(f'The generated login email {system_email} is already in use; choose another username.')
        user = User.objects.create_user(
            school_email=system_email,
            first_name=first_name,
            last_name=last_name,
            username=username,
            personal_email=options['email'],
            password=options['password'],
            is_community_account=True,
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created community account {user.get_full_name()} (login: {system_email}).'
        ))
