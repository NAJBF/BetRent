import os

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allows access only to users with the 'admin' role."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsLandlord(BasePermission):
    """Allows access only to users with the 'landlord' role (or admin)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ("landlord", "admin")
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allows access if the requesting user
    is the object owner or an admin.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True
        for attr in ("owner", "renter", "reviewer", "user"):
            owner = getattr(obj, attr, None)
            if owner is not None:
                return owner == request.user
        return False


class HasPaymentAppToken(BasePermission):
    """
    Static app token for the external payment record endpoint only.
    Send header: X-App-Token: <PAYMENT_APP_TOKEN>
    """

    def has_permission(self, request, view):
        expected = getattr(settings, "PAYMENT_APP_TOKEN", "") or os.environ.get(
            "PAYMENT_APP_TOKEN", ""
        )
        if not expected:
            return False
        token = request.headers.get("X-App-Token") or request.headers.get(
            "Authorization", ""
        ).replace("Bearer ", "").strip()
        return token == expected
