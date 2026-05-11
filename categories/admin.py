from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Category


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "icon", "parent", "created_at"]
    list_filter = ["parent"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["name"]
    autocomplete_fields = ["parent"]
