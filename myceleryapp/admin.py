from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "reg_no",
        "first_name",
        "last_name",
        "email",
        "department",
        "level",
        "user",
        "created_at",
    )

    list_filter = ("department", "level", "created_at")
    search_fields = (
        "reg_no",
        "first_name",
        "last_name",
        "email",
    )

    ordering = ("-created_at",)

    readonly_fields = ("created_at",)

    fieldsets = (
        ("Account", {
            "fields": ("user", "reg_no"),
        }),
        ("Personal Information", {
            "fields": ("first_name", "last_name", "email"),
        }),
        ("Academic Information", {
            "fields": ("department", "level"),
        }),
        ("Timestamps", {
            "fields": ("created_at",),
        }),
    )