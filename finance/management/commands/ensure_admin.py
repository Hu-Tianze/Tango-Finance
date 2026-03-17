import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Ensure a superuser admin account exists (creates one if missing)'

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get('DJANGO_ADMIN_EMAIL', 'admin@test.com')
        password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')

        if not password:
            self.stdout.write('DJANGO_ADMIN_PASSWORD not set, skipping admin creation.')
            return

        if User.objects.filter(email=email).exists():
            u = User.objects.get(email=email)
            if not u.is_superuser:
                u.is_superuser = True
                u.is_staff = True
                u.save()
                self.stdout.write(f'Promoted {email} to superuser.')
            else:
                self.stdout.write(f'Admin {email} already exists.')
        else:
            User.objects.create_superuser(email=email, password=password)
            self.stdout.write(f'Created superuser: {email}')
