from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Review


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ["listing", "reviewer", "rating", "created_at"]
    list_filter = ["rating"]
    search_fields = ["listing__title", "reviewer__email", "comment"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
