"""
BizYangu — customer ledger views (Build Plan v3, Phase 12).
"""

from django.db import transaction as db_transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager
from apps.core.messages import MESSAGES
from .models import Customer, CustomerPayment
from .serializers import (
    CustomerSerializer,
    CustomerCreateSerializer,
    CustomerPaymentSerializer,
    SettlementCreateSerializer,
)
from .services import customer_balance, oldest_outstanding_sale_date


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response({'detail': MESSAGES['BUSINESS_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)
    return business, None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def customer_list_create(request):
    """
    GET /api/v1/customers/?owing=true&sort=amount|age|name
    List customers. `owing=true` is the Phase 12 "creditor list" — only
    customers with balance > 0, sortable by amount owed or by age (how
    long the oldest unpaid credit sale has been outstanding).

    POST /api/v1/customers/
    Quick-add a customer — open to any staff role (cashiers create these
    on the fly mid-sale when a regular buys on credit), unlike settling a
    payment which stays owner/manager only.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    if request.method == 'POST':
        serializer = CustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data.get('phone', '').strip()
        if phone and Customer.objects.filter(business=business, phone=phone, is_active=True).exists():
            return Response({'detail': MESSAGES['CUSTOMER_PHONE_IN_USE']}, status=status.HTTP_400_BAD_REQUEST)
        customer = serializer.save(business=business)
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)

    owing_only = request.query_params.get('owing', '').lower() == 'true'
    sort = request.query_params.get('sort', 'name')

    customers = list(Customer.objects.filter(business=business, is_active=True))
    rows = []
    for c in customers:
        balance = customer_balance(c)
        if owing_only and balance <= 0:
            continue
        oldest = oldest_outstanding_sale_date(c) if balance > 0 else None
        rows.append((c, balance, oldest))

    if sort == 'amount':
        rows.sort(key=lambda r: r[1], reverse=True)
    elif sort == 'age':
        # Oldest outstanding sale first; customers with no outstanding
        # sale (None) sort last regardless of direction.
        rows.sort(key=lambda r: (r[2] is None, r[2]))
    else:
        rows.sort(key=lambda r: r[0].name.lower())

    data = []
    for c, balance, oldest in rows:
        item = CustomerSerializer(c).data
        item['balance'] = str(balance)
        item['oldest_unpaid_at'] = oldest.isoformat() if oldest else None
        data.append(item)

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def customer_detail(request, customer_id):
    """
    GET /api/v1/customers/{id}/
    Full ledger for one customer: current balance, every CREDIT sale
    against it, and every payment recorded. (Sale history uses
    TransactionSerializer via a local import to avoid a hard app-level
    import cycle between transactions and customers.)
    """
    from apps.transactions.models import Transaction
    from apps.transactions.serializers import TransactionSerializer

    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        customer = Customer.objects.get(id=customer_id, business=business)
    except Customer.DoesNotExist:
        return Response({'detail': MESSAGES['CUSTOMER_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    sales = Transaction.objects.filter(
        customer=customer, type=Transaction.Type.SALE,
        payment_method=Transaction.PaymentMethod.CREDIT,
    ).order_by('-created_at')
    payments = customer.payments.all()

    data = CustomerSerializer(customer).data
    data['sales'] = TransactionSerializer(sales, many=True).data
    data['payments'] = CustomerPaymentSerializer(payments, many=True).data
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def settle_payment(request, customer_id):
    """
    POST /api/v1/customers/{id}/settle/
    Record a payment against the customer's outstanding balance. Mirrors
    the refund flow: single amount field, capped at what's actually owed.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    try:
        customer = Customer.objects.get(id=customer_id, business=business)
    except Customer.DoesNotExist:
        return Response({'detail': MESSAGES['CUSTOMER_NOT_FOUND']}, status=status.HTTP_404_NOT_FOUND)

    serializer = SettlementCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    amount = serializer.validated_data['amount']
    notes = serializer.validated_data.get('notes', '')

    balance = customer_balance(customer)
    if amount > balance:
        return Response(
            {'detail': MESSAGES['SETTLEMENT_AMOUNT_EXCEEDS_BALANCE'].format(amount=amount, balance=balance)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # The response payload (including the MESSAGES[] lookup and the
    # serializer call) is built INSIDE the atomic block on purpose. This
    # was the exact cause of a real incident: MESSAGES['SETTLEMENT_RECORDED']
    # didn't exist, so this raised a KeyError *after* the payment had
    # already committed, on an earlier version of this file — the payment
    # was silently created every time, but the caller only ever saw a 500
    # and never knew it had worked. Building the payload here means any
    # future exception in this block (a missing key, a serializer bug,
    # whatever) rolls the payment back with it — a real failure now looks
    # like a real failure, not a phantom success.
    with db_transaction.atomic():
        payment = CustomerPayment.objects.create(
            business=business, customer=customer, amount=amount,
            notes=notes, created_by=request.user,
        )
        response_payload = {
            'detail': MESSAGES['SETTLEMENT_RECORDED'],
            'payment': CustomerPaymentSerializer(payment).data,
            'remaining_balance': str(customer_balance(customer)),
        }

    return Response(response_payload)
