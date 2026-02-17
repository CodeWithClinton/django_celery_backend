import os
from django.conf import settings
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status

from myceleryapp.models import Student
from myceleryapp.serializers import StudentSerializer
from .tasks import process_students_csv
from celery.result import AsyncResult
from mysite.celery import app


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload_students_csv(request):
    file = request.FILES.get("file")

    if not file:
        return Response(
            {"error": "CSV file is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Ensure media folder exists
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)


    # Save file locally
    file_path = os.path.join(settings.MEDIA_ROOT, file.name)

    with open(file_path, "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    # Trigger Celery task
    task = process_students_csv.delay(file_path)

    return Response(
        {
            "message": "CSV upload received. Processing started.",
            "task_id": task.id,
            "status": "PENDING"
        },
        status=status.HTTP_202_ACCEPTED
    )



@api_view(["GET"])
def get_task_status(request, task_id):
    result = AsyncResult(task_id, app=app)

    return Response(
        {
            "task_id": task_id,
            "status": result.status
        }
    )

@api_view(["GET"])
def get_students(request):
    students = Student.objects.all()
    serializer = StudentSerializer(students, many=True)
    return Response(serializer.data)
