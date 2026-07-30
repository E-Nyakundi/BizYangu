"""
BizYangu — customer ledger balance computation (Phase 12).

Balance is always computed here, never stored (see models.py docstring).
Kept as small standalone functions rather than model methods/properties
so they can be called both per-customer (detail view) and reused by the
creditor list without importing DRF anywhere near models.py.
"""

from decimal import Decimal
from django.db.models import Sum, Min


def customer_balance(customer):
    """Outstanding KES this customer owes: CREDIT sales - refunds against
    those sales - payments recorded. Every term excludes voided
    transactions, same as everywhere else in the app treats voids as if
    they never happened."""
    from apps.transactions.models import Transaction

    sales = Transaction.objects.filter(
        customer=customer,
        type=Transaction.Type.SALE,
        payment_method=Transaction.PaymentMethod.CREDIT,
        is_voided=False,
    ).aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')

    refunds = Transaction.objects.filter(
        original_transaction__customer=customer,
        original_transaction__payment_method=Transaction.PaymentMethod.CREDIT,
        type=Transaction.Type.REFUND,
        is_voided=False,
    ).aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')

    payments = customer.payments.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    balance = sales - refunds - payments
    return balance.quantize(Decimal('0.01'))


def oldest_outstanding_sale_date(customer):
    """
    Date of the customer's earliest CREDIT sale, used as the "age" sort
    key for the creditor list. Approximate on purpose (Phase 12 settles
    against the total balance, not per-sale, so there's no exact per-sale
    "this one is still unpaid" flag to sort by) — the oldest credit sale
    is a reasonable proxy for "how long has this person owed us money."
    Returns None if the customer has never had a CREDIT sale.
    """
    from apps.transactions.models import Transaction

    result = Transaction.objects.filter(
        customer=customer,
        type=Transaction.Type.SALE,
        payment_method=Transaction.PaymentMethod.CREDIT,
        is_voided=False,
    ).aggregate(d=Min('created_at'))['d']
    return result


def customer_summary(customer):
    balance = customer_balance(customer)
    oldest = oldest_outstanding_sale_date(customer) if balance > 0 else None
    return balance, oldest
