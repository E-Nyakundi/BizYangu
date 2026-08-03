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
    """Outstanding KES this customer owes: CREDIT/MIXED sales' credit
    portion - refunds against those sales - payments recorded. Every term
    excludes voided transactions, same as everywhere else in the app
    treats voids as if they never happened.

    Sums credit_amount rather than total_amount (item D13) — for a plain
    CREDIT sale the two are equal, but a MIXED sale's credit_amount is
    only part of the total, and only that part is actually owed.
    """
    from apps.transactions.models import Transaction

    sales = Transaction.objects.filter(
        customer=customer,
        type=Transaction.Type.SALE,
        payment_method__in=[Transaction.PaymentMethod.CREDIT, Transaction.PaymentMethod.MIXED],
        is_voided=False,
    ).aggregate(t=Sum('credit_amount'))['t'] or Decimal('0.00')

    # NOTE: refunds against a MIXED sale are apportioned against
    # total_amount here, same as before this change — there's no
    # per-line record of which payment method a refunded item's money
    # originally came from, so a refund on a MIXED sale is treated as
    # coming entirely out of the credit portion first up to its size.
    # This can undercount in edge cases (e.g. refunding an item that was
    # actually paid for in cash, on a sale that also had some credit) —
    # flagging as a known limitation rather than silently getting it
    # wrong in a way that's hard to notice.
    refunds = Transaction.objects.filter(
        original_transaction__customer=customer,
        original_transaction__payment_method__in=[Transaction.PaymentMethod.CREDIT, Transaction.PaymentMethod.MIXED],
        type=Transaction.Type.REFUND,
        is_voided=False,
    ).aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')

    payments = customer.payments.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    balance = sales - refunds - payments
    return balance.quantize(Decimal('0.01'))


def oldest_outstanding_sale_date(customer):
    """
    Date of the customer's earliest CREDIT/MIXED sale, used as the "age"
    sort key for the creditor list. Approximate on purpose (Phase 12
    settles against the total balance, not per-sale, so there's no exact
    per-sale "this one is still unpaid" flag to sort by) — the oldest
    credit sale is a reasonable proxy for "how long has this person owed
    us money." Returns None if the customer has never had a CREDIT/MIXED
    sale with a credit portion.
    """
    from apps.transactions.models import Transaction

    result = Transaction.objects.filter(
        customer=customer,
        type=Transaction.Type.SALE,
        payment_method__in=[Transaction.PaymentMethod.CREDIT, Transaction.PaymentMethod.MIXED],
        is_voided=False,
    ).aggregate(d=Min('created_at'))['d']
    return result


def customer_summary(customer):
    balance = customer_balance(customer)
    oldest = oldest_outstanding_sale_date(customer) if balance > 0 else None
    return balance, oldest
