"""
BizYangu — payments views.
STK Push initiation (authenticated, from the POS), Daraja webhooks
(public, IP-allowlisted), and the reconciliation endpoints the owner
uses to review unmatched M-Pesa payments.
"""

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager
from apps.business.models import Business
from apps.core.messages import MESSAGES
from apps.transactions.models import Transaction
from . import services
from .daraja import DarajaError
from .models import MPesaSTKRequest, MPesaTransaction
from .security import safaricom_ip_required
from .serializers import (
    MPesaTransactionSerializer,
    ReconcileSerializer,
    STKPushRequestSerializer,
    STKRequestSerializer,
)

logger = logging.getLogger(__name__)


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


# ── STK Push (authenticated — initiated from the POS) ──────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def initiate_stk_push(request):
    """
    POST /api/v1/payments/mpesa/stk-push/
    Body: { transaction_id, phone_number }

    The sale must already exist as a PENDING M-Pesa transaction (created
    via POST /transactions/sale/ with payment_method=MPESA — stock is
    deducted at that point same as any sale). This endpoint just sends
    the prompt to the customer's phone; the actual confirmation comes
    back later via the callback webhook below, or by the POS falling
    back to "type in the M-Pesa code manually" if the prompt fails.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = STKPushRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        txn = Transaction.objects.get(
            id=data['transaction_id'], business=business,
            type=Transaction.Type.SALE, is_voided=False,
        )
    except Transaction.DoesNotExist:
        return Response({'detail': MESSAGES['TRANSACTION_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    if txn.payment_method != Transaction.PaymentMethod.MPESA:
        return Response(
            {'detail': MESSAGES['TRANSACTION_NOT_MPESA']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if txn.payment_status != Transaction.PaymentStatus.PENDING:
        return Response(
            {'detail': MESSAGES['TRANSACTION_ALREADY_PROCESSED']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if MPesaSTKRequest.objects.filter(transaction=txn, status=MPesaSTKRequest.Status.PENDING).exists():
        return Response(
            {'detail': MESSAGES['STK_REQUEST_ALREADY_PENDING']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        stk_request = services.initiate_stk_push(transaction=txn, phone_number=data['phone_number'])
    except DarajaError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(STKRequestSerializer(stk_request).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def stk_status(request, checkout_request_id):
    """
    GET /api/v1/payments/mpesa/stk-push/{checkout_request_id}/status/
    Polling fallback for clients without a WebSocket connection (or
    while it's reconnecting). The POS calls this every few seconds
    while showing "Inasubiri malipo..." if the WS update hasn't
    arrived yet.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        stk_request = MPesaSTKRequest.objects.get(
            checkout_request_id=checkout_request_id, business=business,
        )
    except MPesaSTKRequest.DoesNotExist:
        return Response({'detail': MESSAGES['STK_REQUEST_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    return Response(STKRequestSerializer(stk_request).data)


# ── Daraja webhooks (public — Safaricom calls these directly) ──────────────────

def _daraja_ack():
    """Daraja expects this exact shape back, or it'll keep retrying."""
    return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@safaricom_ip_required
def stk_callback(request):
    """
    POST /api/v1/payments/mpesa/callback/
    Safaricom posts the result of an STK Push here. Always ack with
    200 — if we don't, Daraja retries the same callback repeatedly.
    Any processing error is logged, not surfaced to Safaricom.
    """
    try:
        services.process_stk_callback(request.data)
    except Exception:
        logger.exception('Failed to process STK callback: %s', request.data)
    return _daraja_ack()


@api_view(['POST'])
@permission_classes([AllowAny])
@safaricom_ip_required
def c2b_confirmation(request):
    """
    POST /api/v1/payments/mpesa/c2b/confirmation/
    Safaricom posts here when money lands on the business's till
    number directly (no STK push involved — customer initiated it
    from their own phone). We record it unconditionally, then try to
    auto-match it to an open sale by amount + time window.
    """
    payload = request.data
    shortcode = str(payload.get('BusinessShortCode', ''))
    business = Business.objects.filter(
        mpesa_business_shortcode=shortcode,
    ).first() or Business.objects.filter(mpesa_till_number=shortcode).first()

    if not business:
        logger.warning('C2B confirmation for unknown shortcode: %s', shortcode)
        return _daraja_ack()

    try:
        services.process_c2b_confirmation(payload, business)
    except Exception:
        logger.exception('Failed to process C2B confirmation: %s', payload)
    return _daraja_ack()


@api_view(['POST'])
@permission_classes([AllowAny])
@safaricom_ip_required
def c2b_validation(request):
    """
    POST /api/v1/payments/mpesa/c2b/validation/
    Daraja calls this BEFORE the confirmation, asking "should I accept
    this payment?" We're not doing pre-payment validation (e.g.
    account number checks) in this prototype, so we accept everything
    — declining here would block the customer's payment outright.
    """
    return _daraja_ack()


# ── Reconciliation (owner/manager) ──────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def mpesa_transaction_list(request):
    """
    GET /api/v1/payments/mpesa/transactions/?matched=false
    Lists M-Pesa money received. Default shows everything; filter
    with ?matched=true / ?matched=false for the reconciliation view.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    qs = MPesaTransaction.objects.filter(business=business).select_related('transaction')

    matched_param = request.query_params.get('matched')
    if matched_param == 'true':
        qs = qs.filter(is_matched=True)
    elif matched_param == 'false':
        qs = qs.filter(is_matched=False)

    page_size = 200
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    offset = (page - 1) * page_size
    total = qs.count()
    qs = qs[offset:offset + page_size]

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': MPesaTransactionSerializer(qs, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def reconcile(request):
    """
    POST /api/v1/payments/mpesa/reconcile/
    Body: { mpesa_transaction_id, transaction_id }
    Manually links an unmatched M-Pesa payment to a sale — for the
    cases auto-match couldn't handle (amount typo, customer paid more
    than 5 minutes later, etc).
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = ReconcileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        mpesa_txn = MPesaTransaction.objects.get(id=data['mpesa_transaction_id'], business=business)
    except MPesaTransaction.DoesNotExist:
        return Response({'detail': MESSAGES['MPESA_TRANSACTION_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    try:
        txn = Transaction.objects.get(id=data['transaction_id'], business=business)
    except Transaction.DoesNotExist:
        return Response({'detail': MESSAGES['TRANSACTION_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    mpesa_txn.transaction = txn
    mpesa_txn.is_matched = True
    mpesa_txn.is_reconciled = True
    mpesa_txn.save(update_fields=['transaction', 'is_matched', 'is_reconciled'])

    txn.payment_status = Transaction.PaymentStatus.CONFIRMED
    txn.mpesa_reference = mpesa_txn.mpesa_receipt_number
    txn.save(update_fields=['payment_status', 'mpesa_reference'])

    return Response(MPesaTransactionSerializer(mpesa_txn).data)