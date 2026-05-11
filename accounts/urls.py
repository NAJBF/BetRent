from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    RefreshTokenView,
    UserProfileView,
    AdminUserListView,
    AdminUserUpdateView,
)

# Auth URLs — mounted at /api/v1/auth/
auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
]

# User URLs — mounted at /api/v1/users/
user_urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user-profile"),
    path("", AdminUserListView.as_view(), name="admin-user-list"),
    path("<uuid:user_id>/", AdminUserUpdateView.as_view(), name="admin-user-update"),
]