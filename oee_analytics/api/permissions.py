"""
API Permissions for OEE Analytics
Role-based access control for API endpoints
"""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    Read-only access for authenticated users.
    """

    def has_permission(self, request, view):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # Write permissions only for admin
        return request.user and request.user.is_staff


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only to owner
        return obj.created_by == request.user if hasattr(obj, 'created_by') else request.user.is_staff


class IsSiteManagerOrReadOnly(permissions.BasePermission):
    """
    Allow site managers to edit their site's data.
    """

    def has_permission(self, request, view):
        # Authenticated users can read
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated

        # Check if user has site manager role
        return request.user and (
            request.user.is_staff or
            hasattr(request.user, 'profile') and request.user.profile.role == 'site_manager'
        )


class CanAcknowledgeFaults(permissions.BasePermission):
    """
    Permission to acknowledge faults (operators and above).
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Any authenticated user can acknowledge
        return request.user and request.user.is_authenticated


class CanManageMLModels(permissions.BasePermission):
    """
    Permission to manage ML models (data scientists and admins).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Read access for all authenticated
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write access for staff or data scientists
        return request.user.is_staff or (
            hasattr(request.user, 'profile') and
            request.user.profile.role in ['data_scientist', 'engineer']
        )


class RateLimitedPermission(permissions.BasePermission):
    """
    Apply rate limiting to API endpoints.
    """
    # This would integrate with django-ratelimit or similar
    # For now, it's a placeholder

    def has_permission(self, request, view):
        # TODO: Implement rate limiting logic
        return True
