from django.urls import path
from . import views


urlpatterns = [
    path("upload-students-csv/", views.upload_students_csv, name="upload_students_csv"),
    path("task-status/<str:task_id>/", views.get_task_status, name="get_task_status"),
    path("students/", views.get_students, name="student_list"),    
]
