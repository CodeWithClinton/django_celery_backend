from rest_framework import serializers
from .models import Student

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields =  ["id", "reg_no", "first_name", "last_name", "email", "department", "level", "user", "created_at"]