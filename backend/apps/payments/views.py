"""
BizYangu — payments views.
STK Push initiation (authenticated, from the POS), Daraja webhooks
(public, IP-allowlisted), and the reconciliation endpoints the owner
uses to review unmatched M-Pesa payments.
"""

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwner, IsOwnerOrManager
from apps.business.models import Business
from apps.core.messages import MESSAGES
from apps.transactions.models import Transaction
from . import daraja, services
from .daraja import DarajaError
from .models import MPesaSTKRequest, MPesaTransaction, SubscriptionPayment, BusinessMpesaCredentials
from .security import safaricom_ip_required
from .serializers import (
    BusinessMpesaCredentialsSerializer,
    MPesaTransactionSerializer,
    ReconcileSerializer,
    STKPushRequestSerializer,
    STKRequestSerializer,
    SubscriptionPaymentRequestSerializer,
    SubscriptionPaymentSerializer,
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
    business = (
        Business.objects.filter(mpesa_business_shortcode=shortcode).first()
        or Business.objects.filter(mpesa_till_number=shortcode).first()
        or Business.objects.filter(mpesa_credentials__shortcode=shortcode).first()
    )

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


# ── Subscription billing (authenticated — business paying BizYangu) ────────────
# Separate credential set (company shortcode) and separate callback
# URL (MPESA_COMPANY_CALLBACK_URL) from everything above, which is all
# about businesses receiving payment from THEIR OWN customers.

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_subscription_payment(request):
    """
    POST /api/v1/payments/mpesa/subscription/stk-push/
    Body: { phone_number, amount, months? }

    Deliberately does NOT require IsNotExpired — a business with a
    lapsed/expired subscription is exactly who needs to hit this
    endpoint to pay and reactivate.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    serializer = SubscriptionPaymentRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if SubscriptionPayment.objects.filter(
        business=business, status=SubscriptionPayment.Status.PENDING,
    ).exists():
        return Response(
            {'detail': MESSAGES['SUBSCRIPTION_PAYMENT_ALREADY_PENDING']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payment = services.initiate_subscription_payment(
            business=business,
            phone_number=data['phone_number'],
            amount=data['amount'],
            months=data['months'],
        )
    except DarajaError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(SubscriptionPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_payment_status(request, checkout_request_id):
    """
    GET /api/v1/payments/mpesa/subscription/stk-push/{checkout_request_id}/status/
    Polling fallback, same pattern as stk_status above.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        payment = SubscriptionPayment.objects.get(
            checkout_request_id=checkout_request_id, business=business,
        )
    except SubscriptionPayment.DoesNotExist:
        return Response({'detail': MESSAGES['SUBSCRIPTION_PAYMENT_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    return Response(SubscriptionPaymentSerializer(payment).data)


@api_view(['POST'])
@permission_classes([AllowAny])
@safaricom_ip_required
def subscription_callback(request):
    """
    POST /api/v1/payments/mpesa/subscription/callback/
    Register THIS url as MPESA_COMPANY_CALLBACK_URL in the company
    Daraja app's settings — not the same URL as mpesa/callback/ above.
    """
    try:
        services.process_subscription_callback(request.data)
    except Exception:
        logger.exception('Failed to process subscription STK callback: %s', request.data)
    return _daraja_ack()


# ── Business M-Pesa credentials (owner-only — a business's own till) ───────────
# Lets a business receive their OWN customers' STK payments directly
# instead of through the shared sales shortcode. Owner-only (not
# manager) since this is real payment-routing credentials, not day-
# to-day operations. See daraja.resolve_sales_credentials() for how
# this plugs into the sale flow once active.

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsOwner])
def business_mpesa_credentials(request):
    """
    GET  /api/v1/payments/mpesa/business-credentials/
    PUT  /api/v1/payments/mpesa/business-credentials/
    Body (PUT): { till_type, shortcode, consumer_key, consumer_secret?,
                  passkey?, env }
    consumer_secret/passkey are optional on PUT — omit or send blank
    to leave the currently-saved value unchanged (so an owner can
    switch till_type without re-typing their secret every time).
    Any change here sets is_active back to False — see /verify/.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    creds, _ = BusinessMpesaCredentials.objects.get_or_create(business=business)

    if request.method == 'GET':
        return Response(BusinessMpesaCredentialsSerializer(creds).data)

    serializer = BusinessMpesaCredentialsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    creds.till_type = data.get('till_type', creds.till_type)
    creds.shortcode = data.get('shortcode', creds.shortcode)
    creds.consumer_key = data.get('consumer_key', creds.consumer_key)
    if data.get('consumer_secret'):
        creds.consumer_secret = data['consumer_secret']
    if data.get('passkey'):
        creds.passkey = data['passkey']
    creds.env = data.get('env', creds.env)
    # Any edit invalidates the previous verification — force re-verify
    # before this credential set can route real customer payments.
    creds.is_active = False
    creds.verified_at = None
    creds.save()

    return Response(
        {**BusinessMpesaCredentialsSerializer(creds).data, 'detail': MESSAGES['MPESA_CREDENTIALS_SAVED']}
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def verify_business_mpesa_credentials(request):
    """
    POST /api/v1/payments/mpesa/business-credentials/verify/
    Confirms the saved credentials actually work against Daraja
    (fetches a real OAuth token — costs nothing, sends no money) and,
    for a Paybill, registers the C2B confirmation/validation URLs so
    Safaricom knows where to send direct-till payments too. Only on
    success does this business's own till start being used for sales
    — see daraja.resolve_sales_credentials().
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        creds = business.mpesa_credentials
    except BusinessMpesaCredentials.DoesNotExist:
        creds = None

    if not creds or not creds.is_configured():
        return Response(
            {'detail': MESSAGES['MPESA_CREDENTIALS_NOT_CONFIGURED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    mpesa_credentials = daraja.business_credentials(business, ignore_active=True)

    try:
        daraja.get_access_token(mpesa_credentials)
        if creds.till_type == BusinessMpesaCredentials.TillType.PAYBILL:
            daraja.register_c2b_urls(credentials=mpesa_credentials)
    except DarajaError as exc:
        return Response(
            {'detail': MESSAGES['MPESA_CREDENTIALS_VERIFY_FAILED'], 'error': str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    creds.is_active = True
    creds.verified_at = timezone.now()
    creds.save(update_fields=['is_active', 'verified_at'])

    return Response(
        {**BusinessMpesaCredentialsSerializer(creds).data, 'detail': MESSAGES['MPESA_CREDENTIALS_VERIFIED']}
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def deactivate_business_mpesa_credentials(request):
    """
    POST /api/v1/payments/mpesa/business-credentials/deactivate/
    Switches back to the shared sales shortcode without deleting the
    saved credentials — e.g. if a business's own till stops working
    and they need sales to keep going while they sort it out.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        creds = business.mpesa_credentials
    except BusinessMpesaCredentials.DoesNotExist:
        return Response(
            {'detail': MESSAGES['MPESA_CREDENTIALS_NOT_CONFIGURED']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    creds.is_active = False
    creds.save(update_fields=['is_active'])

    return Response(
        {**BusinessMpesaCredentialsSerializer(creds).data, 'detail': MESSAGES['MPESA_CREDENTIALS_DEACTIVATED']}
    )


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