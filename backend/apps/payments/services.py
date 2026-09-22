"""
BizYangu — payments services.

All the actual M-Pesa business logic lives here so views.py stays a
thin HTTP layer. Three jobs:

1. Kick off an STK Push for a pending sale.
2. Process the STK callback Daraja sends back (success or failure).
3. Process C2B confirmations (till-number payments with no STK push
   involved) and try to auto-match them to an open sale.

Every function here is written to be safe to call from a view AND
safe to retry — Daraja can and will call the callback URL more than
once for the same transaction, so everything keys off unique fields
(checkout_request_id, mpesa_receipt_number) and uses explicit
duplicate checks rather than blind .create().
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.transactions.models import Transaction
from apps.inventory.models import StockMovement
from . import daraja
from .daraja import DarajaError  # noqa: F401 — re-exported for views.py
from .models import MPesaSTKRequest, MPesaTransaction, SubscriptionPayment
from .sms_parser import parse_mpesa_sms, SmsClassification

logger = logging.getLogger(__name__)


def _broadcast(business_id, payload: dict) -> None:
    """
    Pushes a payment-status update to the POS screen over WebSocket.
    Fails silently if Channels/Redis isn't reachable — the frontend
    falls back to polling (see lib/payments.ts), so a dropped
    broadcast degrades the UX but never breaks the sale.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            f'mpesa_business_{business_id}',
            {'type': 'mpesa.update', 'payload': payload},
        )
    except Exception:
        logger.exception('WebSocket broadcast failed for business %s', business_id)


def initiate_stk_push(*, transaction: Transaction, phone_number: str) -> MPesaSTKRequest:
    """
    Starts an STK Push for an already-created SALE transaction sitting
    at payment_status=PENDING. Raises DarajaError on failure — the
    caller (view) is responsible for turning that into an HTTP error;
    the Transaction itself is left untouched (still PENDING) so the
    cashier can retry or fall back to cash.
    """
    response = daraja.stk_push(
        credentials=daraja.resolve_sales_credentials(transaction.business),
        phone_number=phone_number,
        amount=transaction.total_amount,
        account_reference=transaction.reference_number,
        transaction_desc=f'BizYangu {transaction.reference_number}',
    )

    stk_request = MPesaSTKRequest.objects.create(
        business=transaction.business,
        transaction=transaction,
        checkout_request_id=response['CheckoutRequestID'],
        merchant_request_id=response['MerchantRequestID'],
        phone_number=daraja.normalize_phone(phone_number),
        amount=transaction.total_amount,
        status=MPesaSTKRequest.Status.PENDING,
    )
    return stk_request


def _void_transaction_for_failed_payment(transaction: Transaction, reason: str) -> None:
    """
    Auto-voids a SALE transaction whose M-Pesa payment failed/timed
    out, restoring stock. A failed STK Push means the customer didn't
    actually pay — there's no reason to hold the stock as sold.
    Mirrors the manual void logic in apps/transactions/views.py.
    """
    if transaction.is_voided:
        return
    with db_transaction.atomic():
        transaction.is_voided = True
        transaction.void_reason = reason
        transaction.payment_status = Transaction.PaymentStatus.FAILED
        transaction.save(update_fields=['is_voided', 'void_reason', 'payment_status'])

        for item in transaction.items.select_related('product').all():
            if item.product.track_stock:
                qty_before = item.product.current_stock
                item.product.current_stock += item.quantity
                item.product.save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    business=transaction.business,
                    product=item.product,
                    transaction=transaction,
                    movement_type=StockMovement.MovementType.REFUND,
                    quantity_change=item.quantity,
                    quantity_before=qty_before,
                    quantity_after=item.product.current_stock,
                    notes=f'Malipo hayakufanikiwa: {transaction.reference_number}',
                    created_by=transaction.created_by,
                )


def process_stk_callback(payload: dict) -> None:
    """
    Handles the Daraja STK callback payload. Shape (per Daraja docs):
    {
      "Body": {
        "stkCallback": {
          "MerchantRequestID": "...",
          "CheckoutRequestID": "...",
          "ResultCode": 0,
          "ResultDesc": "...",
          "CallbackMetadata": {
            "Item": [
              {"Name": "Amount", "Value": 200},
              {"Name": "MpesaReceiptNumber", "Value": "NLJ..."},
              {"Name": "TransactionDate", "Value": 20260627101530},
              {"Name": "PhoneNumber", "Value": 254712345678}
            ]
          }
        }
      }
    }
    ResultCode 0 = success. Anything else = failed/cancelled by user.
    """
    body = (payload or {}).get('Body', {}).get('stkCallback', {})
    checkout_id = body.get('CheckoutRequestID')
    if not checkout_id:
        logger.warning('STK callback missing CheckoutRequestID: %s', payload)
        return

    try:
        stk_request = MPesaSTKRequest.objects.select_related('transaction', 'business').get(
            checkout_request_id=checkout_id,
        )
    except MPesaSTKRequest.DoesNotExist:
        logger.warning('STK callback for unknown CheckoutRequestID: %s', checkout_id)
        return

    if stk_request.status != MPesaSTKRequest.Status.PENDING:
        # Daraja retried a callback we already processed — ignore.
        return

    result_code = body.get('ResultCode')
    result_desc = body.get('ResultDesc', '')
    transaction = stk_request.transaction

    if result_code == 0:
        items = {i['Name']: i.get('Value') for i in body.get('CallbackMetadata', {}).get('Item', [])}
        receipt = items.get('MpesaReceiptNumber', '')

        with db_transaction.atomic():
            stk_request.status = MPesaSTKRequest.Status.SUCCESS
            stk_request.result_code = str(result_code)
            stk_request.result_desc = result_desc
            stk_request.completed_at = timezone.now()
            stk_request.save(update_fields=['status', 'result_code', 'result_desc', 'completed_at'])

            if receipt and not MPesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists():
                MPesaTransaction.objects.create(
                    business=stk_request.business,
                    transaction=transaction,
                    mpesa_receipt_number=receipt,
                    phone_number=str(items.get('PhoneNumber', stk_request.phone_number)),
                    amount=Decimal(str(items.get('Amount', stk_request.amount))),
                    transaction_date=timezone.now(),
                    transaction_type=MPesaTransaction.TransactionType.STK_PUSH,
                    is_matched=True,
                    is_reconciled=True,
                    raw_payload=payload,
                )

            transaction.payment_status = Transaction.PaymentStatus.CONFIRMED
            transaction.mpesa_reference = receipt
            transaction.save(update_fields=['payment_status', 'mpesa_reference'])

        _broadcast(stk_request.business_id, {
            'type': 'stk_result',
            'checkout_request_id': checkout_id,
            'transaction_id': str(transaction.id),
            'status': 'CONFIRMED',
            'mpesa_receipt': receipt,
        })
    else:
        stk_request.status = MPesaSTKRequest.Status.FAILED
        stk_request.result_code = str(result_code)
        stk_request.result_desc = result_desc
        stk_request.completed_at = timezone.now()
        stk_request.save(update_fields=['status', 'result_code', 'result_desc', 'completed_at'])

        _void_transaction_for_failed_payment(
            transaction, reason=f'M-Pesa STK Push imeshindwa: {result_desc}'
        )

        _broadcast(stk_request.business_id, {
            'type': 'stk_result',
            'checkout_request_id': checkout_id,
            'transaction_id': str(transaction.id),
            'status': 'FAILED',
            'mpesa_receipt': None,
            'result_desc': result_desc,
        })


MATCH_WINDOW_MINUTES = 5


def void_stale_pending_stk_requests(timeout_minutes: int = None) -> int:
    """
    Closes out any STK Push still sitting PENDING after `timeout_minutes`
    with no Daraja callback ever received (dropped tunnel, customer
    ignored the prompt, network hiccup) — marks the STK request TIMEOUT
    and voids the underlying sale, restoring stock, via the same helper
    the FAILED-callback path already uses (`_void_transaction_for_failed_
    payment`). Never double-voids: if a late callback resolved the
    transaction some other way between the query and now, this only
    closes out the STK request record.

    Meant to run periodically — see apps.payments.tasks and
    CELERY_BEAT_SCHEDULE in settings/base.py. Safe to call repeatedly;
    idempotent by construction since it only ever touches rows still
    PENDING past the cutoff.
    """
    from django.conf import settings as django_settings

    minutes = timeout_minutes if timeout_minutes is not None else getattr(
        django_settings, 'STK_TIMEOUT_MINUTES', 10
    )
    cutoff = timezone.now() - timedelta(minutes=minutes)

    stale = MPesaSTKRequest.objects.select_related('transaction', 'business').filter(
        status=MPesaSTKRequest.Status.PENDING,
        created_at__lte=cutoff,
    )

    voided_count = 0
    for stk_request in stale:
        transaction = stk_request.transaction

        if transaction.is_voided or transaction.payment_status != Transaction.PaymentStatus.PENDING:
            # Already resolved some other way (e.g. a late callback that
            # slipped in between the query and now) — just close out the
            # STK request record, don't touch the transaction again.
            stk_request.status = MPesaSTKRequest.Status.TIMEOUT
            stk_request.completed_at = timezone.now()
            stk_request.save(update_fields=['status', 'completed_at'])
            continue

        stk_request.status = MPesaSTKRequest.Status.TIMEOUT
        stk_request.result_desc = f'No callback received within {minutes} minutes'
        stk_request.completed_at = timezone.now()
        stk_request.save(update_fields=['status', 'result_desc', 'completed_at'])

        _void_transaction_for_failed_payment(
            transaction,
            reason=f'M-Pesa STK Push haikujibiwa ndani ya dakika {minutes} (muda umeisha)',
        )
        voided_count += 1

        _broadcast(stk_request.business_id, {
            'type': 'stk_result',
            'checkout_request_id': stk_request.checkout_request_id,
            'transaction_id': str(transaction.id),
            'status': 'TIMEOUT',
            'mpesa_receipt': None,
            'result_desc': stk_request.result_desc,
        })
        logger.info(
            'Auto-voided stale PENDING M-Pesa sale %s after %s minutes (STK timeout)',
            transaction.reference_number, minutes,
        )

    return voided_count


def _try_auto_match(mpesa_txn: MPesaTransaction) -> bool:
    """
    Looks for an open (PENDING, not voided) SALE transaction on the
    same business, same amount, created within ±5 minutes of the
    M-Pesa transaction date. This is for the till-number flow — the
    customer pays directly at the till without an STK prompt, so the
    only way to link the payment to a sale is amount + time.

    Returns True if a match was found and linked.
    """
    window_start = mpesa_txn.transaction_date - timedelta(minutes=MATCH_WINDOW_MINUTES)
    window_end = mpesa_txn.transaction_date + timedelta(minutes=MATCH_WINDOW_MINUTES)

    candidates = Transaction.objects.filter(
        business=mpesa_txn.business,
        type=Transaction.Type.SALE,
        payment_method=Transaction.PaymentMethod.MPESA,
        payment_status=Transaction.PaymentStatus.PENDING,
        is_voided=False,
        total_amount=mpesa_txn.amount,
        created_at__gte=window_start,
        created_at__lte=window_end,
    ).order_by('created_at')

    match = candidates.first()
    if not match:
        return False

    with db_transaction.atomic():
        mpesa_txn.transaction = match
        mpesa_txn.is_matched = True
        mpesa_txn.is_reconciled = True
        mpesa_txn.save(update_fields=['transaction', 'is_matched', 'is_reconciled'])

        match.payment_status = Transaction.PaymentStatus.CONFIRMED
        match.mpesa_reference = mpesa_txn.mpesa_receipt_number
        match.save(update_fields=['payment_status', 'mpesa_reference'])

    _broadcast(mpesa_txn.business_id, {
        'type': 'payment_received',
        'mpesa_transaction_id': str(mpesa_txn.id),
        'amount': str(mpesa_txn.amount),
        'phone': mpesa_txn.phone_number,
        'is_matched': True,
    })
    return True


def process_c2b_confirmation(payload: dict, business) -> MPesaTransaction:
    """
    Handles a Daraja C2B confirmation payload (till-number payment).
    Shape (per Daraja docs):
    {
      "TransID": "NLJ...", "TransAmount": "200.00",
      "TransTime": "20260627101530", "MSISDN": "254712345678", ...
    }
    Always creates an MPesaTransaction (the source of truth for "money
    that arrived"), then attempts to auto-match it to an open sale.
    Idempotent on TransID — a duplicate confirmation just returns the
    existing row instead of erroring.
    """
    receipt = payload.get('TransID', '')
    existing = MPesaTransaction.objects.filter(mpesa_receipt_number=receipt).first()
    if existing:
        return existing

    trans_time_raw = payload.get('TransTime', '')
    try:
        trans_date = timezone.make_aware(
            timezone.datetime.strptime(trans_time_raw, '%Y%m%d%H%M%S')
        )
    except (ValueError, TypeError):
        trans_date = timezone.now()

    mpesa_txn = MPesaTransaction.objects.create(
        business=business,
        mpesa_receipt_number=receipt or f'UNKNOWN-{timezone.now().timestamp()}',
        phone_number=payload.get('MSISDN', ''),
        amount=Decimal(str(payload.get('TransAmount', '0'))),
        transaction_date=trans_date,
        transaction_type=MPesaTransaction.TransactionType.C2B,
        is_matched=False,
        is_reconciled=False,
        raw_payload=payload,
    )

    _try_auto_match(mpesa_txn)
    return mpesa_txn


def process_sms_confirmation(raw_sms_text: str, business) -> tuple:
    """
    Handles an M-Pesa confirmation SMS forwarded by the business's own
    device (not a Daraja server callback — see the module docstring in
    sms_parser.py and PHASE_6_SMS_RECONCILIATION_HANDOFF.md for why
    this has to be a separate path from process_c2b_confirmation).

    Trust model is different from C2B on purpose: the caller (view) is
    responsible for authenticating the request as the business's own
    logged-in device (IsAuthenticated), not an IP allowlist — there is
    no Safaricom-to-BizYangu channel here, only the phone self-reporting
    what its own SMS inbox received.

    Returns (MPesaTransaction | None, ParsedSms). The MPesaTransaction
    is None whenever the SMS wasn't a "received" message (sent,
    withdrawal, failed, or unrecognized) — that's an expected, common
    outcome, not an error; the caller should respond success either
    way and use the ParsedSms.reason for logging/diagnostics, exactly
    like the "ignore validation" spirit of c2b_validation. Idempotent
    on the receipt number, same pattern as process_c2b_confirmation:
    a retried/duplicate submission of the same SMS returns the
    existing row rather than erroring or double-recording.
    """
    parsed = parse_mpesa_sms(raw_sms_text)

    if parsed.classification != SmsClassification.RECEIVED:
        logger.info(
            'SMS confirmation for business %s not reconciliation-relevant (%s): %s',
            business.id, parsed.classification.value, parsed.reason,
        )
        return None, parsed

    existing = MPesaTransaction.objects.filter(mpesa_receipt_number=parsed.receipt_number).first()
    if existing:
        return existing, parsed

    raw_payload = {
        'sms_text': raw_sms_text,
        'account_reference': parsed.account_reference,
        'sender_name': parsed.sender_name,
    }

    mpesa_txn = MPesaTransaction.objects.create(
        business=business,
        mpesa_receipt_number=parsed.receipt_number,
        phone_number=parsed.phone_number or '',
        amount=parsed.amount,
        transaction_date=timezone.make_aware(parsed.transaction_date)
        if timezone.is_naive(parsed.transaction_date) else parsed.transaction_date,
        transaction_type=MPesaTransaction.TransactionType.SMS,
        is_matched=False,
        is_reconciled=False,
        raw_payload=raw_payload,
    )

    _try_auto_match(mpesa_txn)
    return mpesa_txn, parsed


# ── Subscription billing (company shortcode — BizYangu's own revenue) ──────────
# Deliberately separate from everything above: those functions are all
# about a business's SALES payments (sales credentials, Transaction/
# MPesaSTKRequest/MPesaTransaction). These two are about a business
# PAYING BIZYANGU (company credentials, SubscriptionPayment). Never
# mix the two — see daraja.default_credentials() vs company_credentials().

def initiate_subscription_payment(*, business, phone_number: str, amount, months: int = 1) -> SubscriptionPayment:
    """
    Starts an STK Push against the COMPANY shortcode for a business's
    subscription fee. Raises DarajaError on failure — the caller
    (view) turns that into an HTTP error. Nothing on Business changes
    yet; that only happens once the callback confirms payment.
    """
    response = daraja.stk_push(
        credentials=daraja.company_credentials(),
        phone_number=phone_number,
        amount=amount,
        account_reference=str(business.id)[:12],
        transaction_desc='BizYangu Sub',
    )

    return SubscriptionPayment.objects.create(
        business=business,
        amount=amount,
        months=months,
        checkout_request_id=response['CheckoutRequestID'],
        merchant_request_id=response['MerchantRequestID'],
        phone_number=daraja.normalize_phone(phone_number),
        status=SubscriptionPayment.Status.PENDING,
    )


def process_subscription_callback(payload: dict) -> None:
    """
    Handles the Daraja STK callback for a subscription payment (same
    payload shape as process_stk_callback above, but this one is
    registered against MPESA_COMPANY_CALLBACK_URL, so it only ever
    receives company-shortcode callbacks). On success: marks the
    SubscriptionPayment SUCCESS and flips the business to ACTIVE.

    NOTE: this sets subscription_status=ACTIVE and subscribed_at=now,
    which — per Business.is_demo_expired() — means the business never
    auto-expires again. Tracking a renewal/lapse date for repeat
    billing (so a business can go from ACTIVE back to EXPIRED after
    `months` runs out) is a separate decision, not made here.
    """
    body = (payload or {}).get('Body', {}).get('stkCallback', {})
    checkout_id = body.get('CheckoutRequestID')
    if not checkout_id:
        logger.warning('Subscription STK callback missing CheckoutRequestID: %s', payload)
        return

    try:
        payment = SubscriptionPayment.objects.select_related('business').get(
            checkout_request_id=checkout_id,
        )
    except SubscriptionPayment.DoesNotExist:
        logger.warning('Subscription STK callback for unknown CheckoutRequestID: %s', checkout_id)
        return

    if payment.status != SubscriptionPayment.Status.PENDING:
        # Daraja retried a callback we already processed — ignore.
        return

    result_code = body.get('ResultCode')
    result_desc = body.get('ResultDesc', '')

    if result_code == 0:
        items = {i['Name']: i.get('Value') for i in body.get('CallbackMetadata', {}).get('Item', [])}
        receipt = items.get('MpesaReceiptNumber', '')

        with db_transaction.atomic():
            payment.status = SubscriptionPayment.Status.SUCCESS
            payment.result_code = str(result_code)
            payment.result_desc = result_desc
            payment.mpesa_receipt_number = receipt
            payment.raw_callback_payload = payload
            payment.completed_at = timezone.now()
            payment.save(update_fields=[
                'status', 'result_code', 'result_desc', 'mpesa_receipt_number',
                'raw_callback_payload', 'completed_at',
            ])

            business = payment.business
            business.subscription_status = business.SubscriptionStatus.ACTIVE
            business.subscribed_at = timezone.now()
            business.save(update_fields=['subscription_status', 'subscribed_at'])

        _broadcast(payment.business_id, {
            'type': 'subscription_result',
            'checkout_request_id': checkout_id,
            'status': 'CONFIRMED',
            'mpesa_receipt': receipt,
        })
    else:
        payment.status = SubscriptionPayment.Status.FAILED
        payment.result_code = str(result_code)
        payment.result_desc = result_desc
        payment.raw_callback_payload = payload
        payment.completed_at = timezone.now()
        payment.save(update_fields=[
            'status', 'result_code', 'result_desc', 'raw_callback_payload', 'completed_at',
        ])

        _broadcast(payment.business_id, {
            'type': 'subscription_result',
            'checkout_request_id': checkout_id,
            'status': 'FAILED',
            'mpesa_receipt': None,
            'result_desc': result_desc,
        })
