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

    Expects the object to have an 'owner' attribute, or falls back
    to checking against common FK names (renter, reviewer, user).
    """

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True
        # Try common owner field names
        for attr in ("owner", "renter", "reviewer", "user"):
            owner = getattr(obj, attr, None)
            if owner is not None:
                return owner == request.user
        return False
