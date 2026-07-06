"""
BizYangu — permission classes.
IsSameBusiness: tenant isolation.
IsNotExpired: demo/subscription enforcement.
Role-based shortcuts: IsOwner, IsOwnerOrManager.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied

from apps.core.messages import MESSAGES


class IsSameBusiness(BasePermission):
    """
    Ensures the requesting user belongs to the same business as the object
    being accessed. Prevents cross-tenant data access.

    Objects must expose a `business` attribute (FK or property).
    """
    message = MESSAGES['CROSS_TENANT_FORBIDDEN']

    def has_object_permission(self, request, view, obj):
        if not hasattr(obj, 'business'):
            return True  # Object not scoped to a business — allow (checked elsewhere)
        if request.user.business is None:
            return False
        return obj.business_id == request.user.business_id


class IsNotExpired(BasePermission):
    """
    Blocks all write operations for businesses with an expired demo.
    Read operations (GET, HEAD, OPTIONS) are always allowed.

    Applied globally to all authenticated viewsets alongside IsSameBusiness.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle unauthenticated requests
        business = getattr(request.user, 'business', None)
        if business and business.is_demo_expired():
            raise PermissionDenied(detail={
                'error': 'demo_expired',
                'message': MESSAGES['DEMO_EXPIRED'],
                'whatsapp': 'https://wa.me/254XXXXXXXXX',
            })
        return True


class IsOwner(BasePermission):
    """Only users with OWNER role."""
    message = MESSAGES['OWNER_ONLY']

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'OWNER'
        )


class IsOwnerOrManager(BasePermission):
    """Users with OWNER or MANAGER role."""
    message = MESSAGES['OWNER_OR_MANAGER_ONLY']

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ('OWNER', 'MANAGER')
        )