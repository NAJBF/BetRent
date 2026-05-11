from django.urls import path
from .views import (
    CategoryListView,
    CategoryDetailView,
    CategoryCreateView,
    CategoryUpdateView,
    CategoryDeleteView,
)

urlpatterns = [
    path("", CategoryListView.as_view(), name="category-list"),
    path("create/", CategoryCreateView.as_view(), name="category-create"),
    path("<slug:slug>/", CategoryDetailView.as_view(), name="category-detail"),
    path("<uuid:category_id>/update/", CategoryUpdateView.as_view(), name="category-update"),
    path("<uuid:category_id>/delete/", CategoryDeleteView.as_view(), name="category-delete"),
]
