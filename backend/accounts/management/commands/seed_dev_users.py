from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update local development users for manual auth testing."

    def handle(self, *args, **options):
        User = get_user_model()
        users = [
            {
                "email": "admin@example.com",
                "password": "Admin123!",
                "full_name": "Admin User",
                "role": User.Role.ADMIN,
                "status": User.Status.ACTIVE,
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "email": "staff@example.com",
                "password": "Staff123!",
                "full_name": "Staff User",
                "role": User.Role.STAFF,
                "status": User.Status.ACTIVE,
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "email": "doctor@example.com",
                "password": "Doctor123!",
                "full_name": "Doctor User",
                "role": User.Role.DOCTOR,
                "status": User.Status.ACTIVE,
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "email": "inactive@example.com",
                "password": "Inactive123!",
                "full_name": "Inactive User",
                "role": User.Role.STAFF,
                "status": User.Status.INACTIVE,
                "is_staff": False,
                "is_superuser": False,
            },
        ]

        for user_data in users:
            email = user_data["email"]
            user = (
                User.objects.filter(username=email).first()
                or User.objects.filter(email=email).first()
            )
            created = user is None
            if created:
                user = User(username=email)

            user.username = email
            user.email = email
            user.full_name = user_data["full_name"]
            user.role = user_data["role"]
            user.status = user_data["status"]
            user.must_change_password = False
            user.is_staff = user_data["is_staff"]
            user.is_superuser = user_data["is_superuser"]
            user.is_active = user.status == User.Status.ACTIVE
            user.set_password(user_data["password"])
            user.save()

            action = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{email}: {action}"))
