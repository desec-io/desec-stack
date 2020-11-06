from ipaddress import IPv4Address, IPv4Network

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


class IsVPNClient(permissions.BasePermission):
    """
    Permission that requires that the user is accessing using an IP from the VPN net.
    """
    message = 'Inadmissible client IP.'

    def has_permission(self, request, view):
        ip = IPv4Address(request.META.get('REMOTE_ADDR'))
        return ip in IPv4Network('10.8.0.0/24')


class ManageTokensPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.auth.perm_manage_tokens


class WithinDomainLimitOnPOST(permissions.BasePermission):
    """
    Permission that requires that the user still has domain limit quota available, if the request is using POST.
    """
    message = 'Domain limit exceeded. Please contact support to create additional domains.'

    def has_permission(self, request, view):
        if request.method != 'POST':
            return True

        return request.user.limit_domains is None or request.user.domains.count() < request.user.limit_domains
