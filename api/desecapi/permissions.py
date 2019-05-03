from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to view or edit it.
    """

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsDomainOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a domain to view or edit an object owned by that domain.
    """

    def has_object_permission(self, request, view, obj):
        return obj.domain.owner == request.user


class IsUnlocked(permissions.BasePermission):
    """
    Allow non-safe methods only when account is not locked.
    """
    message = 'You cannot modify DNS data while your account is locked.'

    def has_permission(self, request, view):
        return bool(
            request.method in permissions.SAFE_METHODS or
            not request.user.locked
        )
