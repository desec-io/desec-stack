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


class WithinDomainLimitOnPOST(permissions.BasePermission):
    """
    Permission that requires that the user still has domain limit quota available, if the request is using POST.
    """
    message = 'Domain limit exceeded. Please contact support to create additional domains.'

    def has_permission(self, request, view):
        if request.method != 'POST':
            return True

        return request.user.limit_domains is None or request.user.domains.count() < request.user.limit_domains
