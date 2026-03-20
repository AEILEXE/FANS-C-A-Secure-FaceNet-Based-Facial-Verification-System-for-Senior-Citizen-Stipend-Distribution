"""
Management command: create_admin
Creates the initial admin user for FANS.

Usage:
    python manage.py create_admin --username admin --password yourpassword
"""
from django.core.management.base import BaseCommand
from accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Create the initial FANS admin user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin')
        parser.add_argument('--password', type=str, default='Admin@1234')
        parser.add_argument('--email', type=str, default='admin@fans.local')
        parser.add_argument('--first-name', type=str, default='System')
        parser.add_argument('--last-name', type=str, default='Admin')

    def handle(self, *args, **options):
        username = options['username']
        if CustomUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Skipping.'))
            return

        user = CustomUser.objects.create_superuser(
            username=username,
            email=options['email'],
            password=options['password'],
            first_name=options['first_name'],
            last_name=options['last_name'],
            role=CustomUser.ROLE_ADMIN,
            employee_id='ADM-001',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Admin user "{username}" created successfully.\n'
            f'Password: {options["password"]}\n'
            f'CHANGE THIS PASSWORD immediately in production!'
        ))
