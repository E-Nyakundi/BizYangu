"""
BizYangu — notifications views.
Device registration for push, and a readback log for the owner/manager
to confirm alerts are actually firing during the pilot.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager
from apps.core.messages import MESSAGES
from .models import DeviceToken, NotificationLog
from .serializers import DeviceTokenSerializer, NotificationLogSerializer


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_device(request):
    """
    POST /api/v1/notifications/devices/
    Body: { token, platform }
    Called by the app on launch (after the user grants push permission).
    Re-registering the same token just refreshes `last_used_at` and
    re-links it to the current user/business — handles the case of a
    cashier logging out and a different user logging in on the same
    phone.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    token = (request.data.get('token') or '').strip()
    platform = (request.data.get('platform') or 'ANDROID').upper()
    if not token:
        return Response({'detail': MESSAGES['TOKEN_REQUIRED']}, status=status.HTTP_400_BAD_REQUEST)
    if platform not in dict(DeviceToken.Platform.choices):
        platform = DeviceToken.Platform.ANDROID

    device, _created = DeviceToken.objects.update_or_create(
        token=token,
        defaults={
            'business': business,
            'user': request.user,
            'platform': platform,
            'is_active': True,
        },
    )

    return Response(DeviceTokenSerializer(device).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unregister_device(request):
    """
    POST /api/v1/notifications/devices/unregister/
    Body: { token }
    Called on logout so a shared/handover device stops getting pushes
    for the previous user's business.
    """
    token = (request.data.get('token') or '').strip()
    if not token:
        return Response({'detail': MESSAGES['TOKEN_REQUIRED']}, status=status.HTTP_400_BAD_REQUEST)

    DeviceToken.objects.filter(token=token, user=request.user).update(is_active=False)
    return Response({'detail': MESSAGES['DEVICE_UNREGISTERED']}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def notification_log(request):
    """
    GET /api/v1/notifications/log/
    Recent low-stock alert attempts for this business — lets the owner
    confirm pushes are actually firing (and see why, if they're not).
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    qs = NotificationLog.objects.filter(business=business).select_related('product')[:100]
    return Response(NotificationLogSerializer(qs, many=True).data)
