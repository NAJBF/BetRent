from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    RefreshTokenView,
    VerifyEmailView,
    ResendOTPView,
    ForgotPasswordView,
    ResetPasswordView,
    UserProfileView,
    AdminUserListView,
    AdminUserUpdateView,
)

# Auth URLs — mounted at /api/v1/auth/
auth_urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("resend-otp/", ResendOTPView.as_view(), name="auth-resend-otp"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
]

# User URLs — mounted at /api/v1/users/
user_urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user-profile"),
    path("", AdminUserListView.as_view(), name="admin-user-list"),
    path("<int:user_id>/", AdminUserUpdateView.as_view(), name="admin-user-update"),
]
