"""
BizYangu — business views.
Business setup, profile management, staff management.
"""

import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsOwner, IsOwnerOrManager, IsSameBusiness, IsNotExpired
from apps.core.messages import MESSAGES
from .models import Business
from .serializers import (
    BusinessSetupSerializer,
    BusinessProfileSerializer,
    BusinessUpdateSerializer,
    StaffMemberSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Business setup (onboarding) ───────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def business_setup(request):
    """
    POST /api/v1/business/setup/
    Creates a business and links it to the current user (OWNER role).
    Can only be called once — if user already has a business, returns 400.
    """
    if request.user.business:
        return Response(
            {'detail': MESSAGES['BUSINESS_ALREADY_REGISTERED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = BusinessSetupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    business = serializer.save(owner=request.user)

    # Link user to their business and set as OWNER
    request.user.business = business
    request.user.role = User.Role.OWNER
    request.user.save(update_fields=['business', 'role'])

    return Response(
        BusinessProfileSerializer(business).data,
        status=status.HTTP_201_CREATED,
    )


# ── Business profile ──────────────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsSameBusiness])
def business_detail(request):
    """
    GET   /api/v1/business/  — Get current business profile.
    PATCH /api/v1/business/  — Update business settings (owner only for PATCH).
    """
    business = request.user.business
    if not business:
        return Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND_CREATE_FIRST']},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(BusinessProfileSerializer(business).data)

    # PATCH — owner only
    if request.user.role != User.Role.OWNER:
        return Response(
            {'detail': MESSAGES['OWNER_PERMISSION_REQUIRED']},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = BusinessUpdateSerializer(business, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(BusinessProfileSerializer(business).data)


# ── Staff management ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwnerOrManager])
def staff_list(request):
    """
    GET /api/v1/business/users/
    List all active staff for the current business.
    """
    business = request.user.business
    if not business:
        return Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    staff = business.staff.filter(is_active=True).order_by('name')
    return Response(StaffMemberSerializer(staff, many=True).data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsOwner])
def staff_remove(request, user_id):
    """
    DELETE /api/v1/business/users/{id}/
    Deactivate a staff member (soft delete). Owner cannot remove themselves.
    """
    business = request.user.business
    if not business:
        return Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    if str(request.user.id) == str(user_id):
        return Response(
            {'detail': MESSAGES['CANNOT_REMOVE_SELF']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        staff_member = business.staff.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return Response(
            {'detail': MESSAGES['STAFF_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )

    staff_member.is_active = False
    staff_member.save(update_fields=['is_active'])
    return Response({'detail': MESSAGES['STAFF_REMOVED']}, status=status.HTTP_200_OK)