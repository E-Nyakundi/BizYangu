"""
BizYangu — reports views.
Every report here is computed fresh from Transaction / TransactionItem /
StockMovement — there's no Report model, per the build plan. Owner/manager
only: this is business intelligence, not something a cashier needs.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired, IsOwnerOrManager
from apps.catalog.models import Product
from apps.core.messages import MESSAGES
from apps.inventory.models import StockMovement
from apps.transactions.models import Transaction

from .serializers import DateQuerySerializer, PeriodQuerySerializer


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response(
            {'detail': MESSAGES['BUSINESS_NOT_FOUND']},
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


# ── Shared helpers ───────────────────────────────────────────────────────────

def _sales_qs(business, date_from, date_to):
    return Transaction.objects.filter(
        business=business, type=Transaction.Type.SALE, is_voided=False,
        created_at__date__gte=date_from, created_at__date__lte=date_to,
    )


def _refunds_qs(business, date_from, date_to):
    return Transaction.objects.filter(
        business=business, type=Transaction.Type.REFUND, is_voided=False,
        created_at__date__gte=date_from, created_at__date__lte=date_to,
    )


def _money_summary(business, date_from, date_to):
    """
    Core numbers every report is built from: gross sales, refunds, net
    revenue, transaction count, and the payment-method breakdown. Net
    revenue is gross SALE total minus REFUND total for the same window —
    refunds are their own transaction type (see the refund feature), so
    they'd otherwise never get subtracted anywhere.
    """
    TWO_PLACES = Decimal('0.01')

    def money(value):
        """Quantize to 2dp. SQLite's Decimal aggregation drops trailing
        zeros (Postgres doesn't) — quantizing keeps the API contract
        (always 'X.XX') stable across both backends."""
        return (value or Decimal('0.00')).quantize(TWO_PLACES)

    sales = _sales_qs(business, date_from, date_to)
    refunds = _refunds_qs(business, date_from, date_to)

    gross = money(sales.aggregate(total=Sum('total_amount'))['total'])
    refunded = money(refunds.aggregate(total=Sum('total_amount'))['total'])
    txn_count = sales.count()
    net = money(gross - refunded)
    avg = money(net / txn_count) if txn_count else Decimal('0.00')

    by_method = {
        row['payment_method']: money(row['total'])
        for row in sales.values('payment_method').annotate(total=Sum('total_amount'))
    }

    return {
        'gross_revenue': str(gross),
        'refunded_amount': str(refunded),
        'net_revenue': str(net),
        'transaction_count': txn_count,
        'average_transaction': str(avg),
        'cash_total': str(by_method.get(Transaction.PaymentMethod.CASH, Decimal('0.00'))),
        'mpesa_total': str(by_method.get(Transaction.PaymentMethod.MPESA, Decimal('0.00'))),
        'credit_total': str(by_method.get(Transaction.PaymentMethod.CREDIT, Decimal('0.00'))),
        'mixed_total': str(by_method.get(Transaction.PaymentMethod.MIXED, Decimal('0.00'))),
    }


def _top_products(business, date_from, date_to, limit=5):
    rows = (
        Transaction.objects.filter(
            business=business, type=Transaction.Type.SALE, is_voided=False,
            created_at__date__gte=date_from, created_at__date__lte=date_to,
        )
        .values('items__product_id', 'items__product__name', 'items__product__unit')
        .annotate(qty_sold=Sum('items__quantity'), revenue=Sum('items__subtotal'))
        .exclude(items__product_id__isnull=True)
        .order_by('-revenue')[:limit]
    )
    return [
        {
            'product_id': str(row['items__product_id']),
            'name': row['items__product__name'],
            'unit': row['items__product__unit'],
            'quantity_sold': str(row['qty_sold']),
            'revenue': str((row['revenue'] or Decimal('0.00')).quantize(Decimal('0.01'))),
        }
        for row in rows
    ]


def _low_stock_summary(business, limit=5):
    products = Product.objects.filter(business=business, is_active=True, track_stock=True)
    low = products.filter(current_stock__gt=0, current_stock__lte=F('low_stock_threshold'))
    out = products.filter(current_stock__lte=0)
    low_count = low.count()
    out_count = out.count()
    sample = list(
        products.filter(Q(current_stock__lte=0) | Q(current_stock__lte=F('low_stock_threshold')))
        .order_by('current_stock')[:limit]
        .values('id', 'name', 'current_stock', 'low_stock_threshold', 'unit')
    )
    return {
        'low_stock_count': low_count,
        'out_of_stock_count': out_count,
        'items': [
            {
                'product_id': str(p['id']),
                'name': p['name'],
                'current_stock': str(p['current_stock']),
                'low_stock_threshold': str(p['low_stock_threshold']),
                'unit': p['unit'],
            }
            for p in sample
        ],
    }


def _loss_summary(business, date_from, date_to):
    movements = StockMovement.objects.filter(
        business=business,
        movement_type__in=[StockMovement.MovementType.LOSS, StockMovement.MovementType.DAMAGE],
        created_at__date__gte=date_from, created_at__date__lte=date_to,
    ).select_related('product')

    by_product = {}
    total_qty = Decimal('0.00')
    total_value = Decimal('0.00')

    for m in movements:
        qty = abs(m.quantity_change)
        unit_value = m.product.cost_price if m.product.cost_price is not None else m.product.selling_price
        value = qty * unit_value
        total_qty += qty
        total_value += value

        entry = by_product.setdefault(m.product_id, {
            'product_id': str(m.product_id),
            'name': m.product.name,
            'unit': m.product.unit,
            'quantity_lost': Decimal('0.00'),
            'estimated_value': Decimal('0.00'),
        })
        entry['quantity_lost'] += qty
        entry['estimated_value'] += value

    breakdown = sorted(by_product.values(), key=lambda r: r['estimated_value'], reverse=True)
    for row in breakdown:
        row['quantity_lost'] = str(row['quantity_lost'])
        row['estimated_value'] = str(row['estimated_value'].quantize(Decimal('0.01')))

    return {
        'total_quantity_lost': str(total_qty),
        'total_estimated_value': str(total_value.quantize(Decimal('0.01'))),
        'by_product': breakdown,
        'by_type': _loss_by_type(movements),
        'by_employee': _loss_by_employee(movements),
    }


def _loss_by_type(movements):
    """
    Loss value grouped by movement_type (LOSS vs DAMAGE) — the plan asks
    for a "by type" breakdown alongside the by-product one. Iterates the
    same movements queryset already fetched by the caller rather than
    re-querying.
    """
    totals = {}
    for m in movements:
        qty = abs(m.quantity_change)
        unit_value = m.product.cost_price if m.product.cost_price is not None else m.product.selling_price
        entry = totals.setdefault(m.movement_type, {'quantity_lost': Decimal('0.00'), 'estimated_value': Decimal('0.00')})
        entry['quantity_lost'] += qty
        entry['estimated_value'] += qty * unit_value

    return [
        {
            'movement_type': movement_type,
            'quantity_lost': str(v['quantity_lost']),
            'estimated_value': str(v['estimated_value'].quantize(Decimal('0.01'))),
        }
        for movement_type, v in sorted(totals.items(), key=lambda kv: kv[1]['estimated_value'], reverse=True)
    ]


def _loss_by_employee(movements):
    """Loss value grouped by the staff member who recorded the movement."""
    totals = {}
    for m in movements:
        qty = abs(m.quantity_change)
        unit_value = m.product.cost_price if m.product.cost_price is not None else m.product.selling_price
        key = m.created_by_id
        entry = totals.setdefault(key, {
            'user_id': str(key) if key else None,
            'name': m.created_by.name if m.created_by_id else 'Unknown',
            'quantity_lost': Decimal('0.00'),
            'estimated_value': Decimal('0.00'),
        })
        entry['quantity_lost'] += qty
        entry['estimated_value'] += qty * unit_value

    breakdown = sorted(totals.values(), key=lambda r: r['estimated_value'], reverse=True)
    for row in breakdown:
        row['quantity_lost'] = str(row['quantity_lost'])
        row['estimated_value'] = str(row['estimated_value'].quantize(Decimal('0.01')))
    return breakdown


# ── Endpoints ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def dashboard(request):
    """
    GET /api/v1/reports/dashboard/
    Today's snapshot for the owner dashboard: revenue, transaction count,
    payment split, top products, low-stock alerts, and a plain
    percentage-vs-yesterday comparison.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    today = timezone.localdate()
    yesterday = today - timezone.timedelta(days=1)

    today_summary = _money_summary(business, today, today)
    yesterday_summary = _money_summary(business, yesterday, yesterday)

    today_net = Decimal(today_summary['net_revenue'])
    yesterday_net = Decimal(yesterday_summary['net_revenue'])
    if yesterday_net > 0:
        change_pct = float((today_net - yesterday_net) / yesterday_net * 100)
    else:
        change_pct = None  # nothing to compare against — frontend just hides the badge

    return Response({
        'date': str(today),
        **today_summary,
        'revenue_change_pct': change_pct,
        'yesterday_net_revenue': yesterday_summary['net_revenue'],
        'top_products': _top_products(business, today, today, limit=5),
        'stock_alert': _low_stock_summary(business, limit=5),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def daily_report(request):
    """GET /api/v1/reports/daily/?date=YYYY-MM-DD (defaults to today)."""
    business, err = get_business_or_404(request)
    if err:
        return err

    q = DateQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    the_date = q.get_date()

    summary = _money_summary(business, the_date, the_date)
    voided_count = Transaction.objects.filter(
        business=business, type=Transaction.Type.SALE, is_voided=True,
        created_at__date=the_date,
    ).count()

    return Response({
        'date': str(the_date),
        **summary,
        'voided_count': voided_count,
        'top_products': _top_products(business, the_date, the_date, limit=10),
        'losses': _loss_summary(business, the_date, the_date),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def period_report(request):
    """GET /api/v1/reports/period/?start=YYYY-MM-DD&end=YYYY-MM-DD (defaults to last 30 days)."""
    business, err = get_business_or_404(request)
    if err:
        return err

    q = PeriodQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    start, end = q.validated_data['start'], q.validated_data['end']

    summary = _money_summary(business, start, end)

    daily_rows = (
        _sales_qs(business, start, end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(revenue=Sum('total_amount'), count=Count('id'))
        .order_by('day')
    )
    daily_breakdown = [
        {
            'date': str(row['day']),
            'revenue': str((row['revenue'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            'transaction_count': row['count'],
        }
        for row in daily_rows
    ]

    return Response({
        'start': str(start),
        'end': str(end),
        **summary,
        'daily_breakdown': daily_breakdown,
        'top_products': _top_products(business, start, end, limit=10),
        'losses': _loss_summary(business, start, end),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def product_performance_report(request):
    """
    GET /api/v1/reports/products/?start=&end= (defaults to last 30 days)
    Revenue, units sold, and margin per product — only products with at
    least one sale in the window. Margin is omitted (null) for products
    with no cost_price set, rather than guessing.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    q = PeriodQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    start, end = q.validated_data['start'], q.validated_data['end']

    rows = (
        Transaction.objects.filter(
            business=business, type=Transaction.Type.SALE, is_voided=False,
            created_at__date__gte=start, created_at__date__lte=end,
        )
        .values('items__product_id', 'items__product__name', 'items__product__unit', 'items__product__cost_price')
        .annotate(qty_sold=Sum('items__quantity'), revenue=Sum('items__subtotal'))
        .exclude(items__product_id__isnull=True)
        .order_by('-revenue')
    )

    TWO_PLACES = Decimal('0.01')
    products = []
    for row in rows:
        revenue = (row['revenue'] or Decimal('0.00')).quantize(TWO_PLACES)
        cost_price = row['items__product__cost_price']
        if cost_price is not None:
            cost_total = (cost_price * row['qty_sold']).quantize(TWO_PLACES)
            margin = (revenue - cost_total).quantize(TWO_PLACES)
            margin_pct = float(margin / revenue * 100) if revenue > 0 else None
        else:
            cost_total = None
            margin = None
            margin_pct = None

        products.append({
            'product_id': str(row['items__product_id']),
            'name': row['items__product__name'],
            'unit': row['items__product__unit'],
            'quantity_sold': str(row['qty_sold']),
            'revenue': str(revenue),
            'cost_total': str(cost_total) if cost_total is not None else None,
            'margin': str(margin) if margin is not None else None,
            'margin_pct': margin_pct,
        })

    return Response({'start': str(start), 'end': str(end), 'products': products})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def loss_report(request):
    """GET /api/v1/reports/losses/?start=&end= (defaults to last 30 days)."""
    business, err = get_business_or_404(request)
    if err:
        return err

    q = PeriodQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    start, end = q.validated_data['start'], q.validated_data['end']

    return Response({'start': str(start), 'end': str(end), **_loss_summary(business, start, end)})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def eod_summary(request):
    """
    GET /api/v1/reports/eod-summary/?date=YYYY-MM-DD (defaults to today)
    Same numbers as the daily report, plus a pre-formatted whatsapp_text
    field — the frontend just needs to hand this string to the share sheet,
    no WhatsApp API integration needed.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    q = DateQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    the_date = q.get_date()

    summary = _money_summary(business, the_date, the_date)
    top = _top_products(business, the_date, the_date, limit=3)
    stock = _low_stock_summary(business, limit=5)

    top_lines = '\n'.join(
        f'{i + 1}. {p["name"]} — {p["quantity_sold"]} sold'
        for i, p in enumerate(top)
    ) or '—'

    text = (
        f'📊 *{business.name} — EOD Summary*\n'
        f'{the_date.strftime("%d %b %Y")}\n\n'
        f'💰 Revenue: KES {summary["net_revenue"]}\n'
        f'🧾 Transactions: {summary["transaction_count"]}\n'
        f'💵 Cash: KES {summary["cash_total"]}\n'
        f'📱 M-Pesa: KES {summary["mpesa_total"]}\n'
        f'↩️ Refunds: KES {summary["refunded_amount"]}\n\n'
        f'🏆 Top sellers:\n{top_lines}\n\n'
        f'⚠️ Low stock: {stock["low_stock_count"]} items, '
        f'{stock["out_of_stock_count"]} out of stock'
    )

    return Response({
        'date': str(the_date),
        **summary,
        'top_products': top,
        'stock_alert': stock,
        'whatsapp_text': text,
    })