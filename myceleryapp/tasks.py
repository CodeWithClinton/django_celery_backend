import csv
from celery import shared_task
from django.contrib.auth import get_user_model

from .models import Student


@shared_task
def process_students_csv(file_path):
    User = get_user_model()

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            reg_no = row.get("reg_no")
            first_name = row.get("first_name")
            last_name = row.get("last_name")
            email = row.get("email")
            department = row.get("department", "")
            level = row.get("level", "")

            # Create user
            user, created = User.objects.get_or_create(
                username=reg_no,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                },
            )

            # Create student
            Student.objects.get_or_create(
                reg_no=reg_no,
                defaults={
                    "user": user,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "department": department,
                    "level": level,
                },
            )
