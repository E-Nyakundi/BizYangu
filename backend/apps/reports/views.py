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
from apps.transactions.models import Transaction, TransactionItem

from .models import BusinessMilestone
from .serializers import BusinessMilestoneSerializer, DateQuerySerializer, PeriodQuerySerializer


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


def _daily_margin_trend(business, date_from, date_to):
    """
    Per-day revenue/cost/margin, built from TransactionItem rows rather than
    Transaction totals (unlike _money_summary's daily_breakdown) because
    margin is only computable at the line-item level where cost_price was
    snapshotted at sale time. Items with no cost_price recorded are excluded
    from the cost/margin sums (same "don't guess" rule as
    product_performance_report) but nothing here fabricates a cost.
    """
    TWO_PLACES = Decimal('0.01')

    rows = (
        TransactionItem.objects.filter(
            transaction__business=business,
            transaction__type=Transaction.Type.SALE,
            transaction__is_voided=False,
            transaction__created_at__date__gte=date_from,
            transaction__created_at__date__lte=date_to,
            cost_price__isnull=False,
        )
        .annotate(day=TruncDate('transaction__created_at'))
        .values('day')
        .annotate(
            revenue=Sum('subtotal'),
            cost=Sum(F('cost_price') * F('quantity')),
        )
        .order_by('day')
    )

    trend = []
    for row in rows:
        revenue = (row['revenue'] or Decimal('0.00')).quantize(TWO_PLACES)
        cost = (row['cost'] or Decimal('0.00')).quantize(TWO_PLACES)
        margin = (revenue - cost).quantize(TWO_PLACES)
        margin_pct = float(margin / revenue * 100) if revenue > 0 else None
        trend.append({
            'date': str(row['day']),
            'revenue': str(revenue),
            'cost': str(cost),
            'margin': str(margin),
            'margin_pct': margin_pct,
        })
    return trend


def _previous_period(start, end):
    """Returns (prev_start, prev_end) — the immediately preceding window of
    the same length as (start, end), inclusive on both sides. Used for the
    period-over-period growth indicator: 'this month vs last month' when
    start/end happen to bound a calendar month, but works for any range."""
    length_days = (end - start).days + 1
    prev_end = start - timezone.timedelta(days=1)
    prev_start = prev_end - timezone.timedelta(days=length_days - 1)
    return prev_start, prev_end


def _pct_change(current, previous):
    """None when there's nothing to compare against (previous == 0) —
    frontend hides the badge rather than showing a misleading ∞ or 0%."""
    if previous > 0:
        return float((current - previous) / previous * 100)
    return None


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
    ).select_related('product', 'created_by')
    # select_related('created_by') matters here even though this function
    # doesn't touch it directly — _loss_by_employee() below iterates this
    # same cached queryset and reads m.created_by.name per row. Without it,
    # that's one extra query per loss/damage movement in the period.

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
def growth_report(request):
    """
    GET /api/v1/reports/growth/?start=&end= (defaults to last 30 days)
    Phase 7 — Reports: growth & profit graphs. Turns the existing
    aggregation into visual trend data:
      - daily_breakdown: revenue-over-time (reuses the same shape as
        /reports/period/, so the frontend's existing chart component works
        unchanged if reused)
      - margin_trend: profit/margin per day, computed at the line-item
        level (see _daily_margin_trend) since Transaction totals alone
        can't carry per-day cost
      - has_margin_data: false when no line item in the window has a
        cost_price set — the frontend should not render margin language
        in that case (e.g. a service business that never set cost prices)
      - business_mode: 'goods' | 'service' — a business counts as 'goods'
        if it has any stock-tracked product OR any margin data in the
        window; otherwise 'service'. Used by the frontend to skip
        stock/margin framing entirely for service-type businesses per the
        build plan's Phase 7 requirement (2.1/2.2) — note there's no
        explicit has_inventory flag on Business yet (that lands in Phase
        9), so this is inferred rather than a stored flag.
      - current_period / previous_period / revenue_growth_pct /
        transaction_growth_pct: period-over-period comparison against the
        immediately preceding window of the same length
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    q = PeriodQuerySerializer(data=request.query_params)
    q.is_valid(raise_exception=True)
    start, end = q.validated_data['start'], q.validated_data['end']

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

    margin_trend = _daily_margin_trend(business, start, end)
    has_margin_data = len(margin_trend) > 0
    has_tracked_products = Product.objects.filter(business=business, track_stock=True).exists()
    business_mode = 'goods' if (has_margin_data or has_tracked_products) else 'service'

    current_summary = _money_summary(business, start, end)
    prev_start, prev_end = _previous_period(start, end)
    previous_summary = _money_summary(business, prev_start, prev_end)

    current_net = Decimal(current_summary['net_revenue'])
    previous_net = Decimal(previous_summary['net_revenue'])
    revenue_growth_pct = _pct_change(current_net, previous_net)
    transaction_growth_pct = _pct_change(
        Decimal(current_summary['transaction_count']),
        Decimal(previous_summary['transaction_count']),
    )

    return Response({
        'start': str(start),
        'end': str(end),
        'daily_breakdown': daily_breakdown,
        'margin_trend': margin_trend,
        'has_margin_data': has_margin_data,
        'business_mode': business_mode,
        'current_period': {
            'net_revenue': current_summary['net_revenue'],
            'transaction_count': current_summary['transaction_count'],
        },
        'previous_period': {
            'start': str(prev_start),
            'end': str(prev_end),
            'net_revenue': previous_summary['net_revenue'],
            'transaction_count': previous_summary['transaction_count'],
        },
        'revenue_growth_pct': revenue_growth_pct,
        'transaction_growth_pct': transaction_growth_pct,
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


# ── Data Health (Phase 13) ──────────────────────────────────────────────────
# One visible number reflecting how complete/trustworthy a business's own
# data is, built entirely from signals that already exist elsewhere in the
# app — this is a summarizing layer, not a new source of information (see
# the design constraints pinned in the pilot-path build plan). Computed on
# read, matching the no-Report-model convention every other report here
# already follows, and the Phase 12 customer-balance pattern.

def _data_health_dimensions(business):
    """
    Returns a list of {key, label, percentage} dicts. `percentage` is
    None when a dimension genuinely doesn't apply yet — e.g. cost-price
    coverage for a business with zero products isn't "bad data," it's
    "no data yet," and averaging it in as 0 would be actively misleading.
    Dimensions with percentage=None are excluded from the overall score,
    not counted against it.
    """
    products = Product.objects.filter(business=business, is_active=True)
    product_count = products.count()

    dimensions = []

    if product_count:
        with_cost = products.exclude(cost_price__isnull=True).count()
        dimensions.append({
            'key': 'cost_price',
            'label': 'Cost price coverage',
            'percentage': round(with_cost / product_count * 100, 1),
            '_missing_count': product_count - with_cost,
        })
    else:
        dimensions.append({'key': 'cost_price', 'label': 'Cost price coverage', 'percentage': None})

    if product_count:
        via_taxonomy = products.filter(created_via=Product.CreationSource.TAXONOMY).count()
        dimensions.append({
            'key': 'taxonomy_depth',
            'label': 'Catalog detail (brand-level entries)',
            'percentage': round(via_taxonomy / product_count * 100, 1),
        })
    else:
        dimensions.append({'key': 'taxonomy_depth', 'label': 'Catalog detail (brand-level entries)', 'percentage': None})

    # Reconciliation cleanliness: among freeform (product IS NULL) sale
    # items ever recorded, what % have been resolved. Deliberately scoped
    # to freeform items only, not all transaction items — a normal
    # catalog sale is already is_reconciled=True by default, so including
    # it would dilute this toward 100% regardless of whether the
    # reconciliation queue is actually being kept clean.
    #
    # Gated on has_any_sale, not just freeform_count==0: a business that
    # has never made a single sale would otherwise show a vacuous 100%
    # here (zero freeform items, so "100% of zero are reconciled" is
    # technically true but means nothing) — that's not a genuine signal,
    # it's an artifact of having nothing to measure yet, and it would
    # incorrectly give a brand-new empty business a real-looking score
    # when every other dimension is correctly None. A business that HAS
    # sold things but never used a freeform item gets a genuine, earned
    # 100% instead.
    has_any_sale = Transaction.objects.filter(business=business, type=Transaction.Type.SALE).exists()
    freeform_items = TransactionItem.objects.filter(transaction__business=business, product__isnull=True)
    freeform_count = freeform_items.count()
    if not has_any_sale:
        reconciliation_pct = None
        reconciled_count = 0
    elif freeform_count:
        reconciled_count = freeform_items.filter(is_reconciled=True).count()
        reconciliation_pct = round(reconciled_count / freeform_count * 100, 1)
    else:
        reconciled_count = 0
        reconciliation_pct = 100.0
    dimensions.append({
        'key': 'reconciliation',
        'label': 'Reconciliation cleanliness',
        'percentage': reconciliation_pct,
        '_freeform_count': freeform_count,
        '_reconciled_count': reconciled_count,
    })

    # Barcode confirmation — deferred until barcode scanning ships (see
    # Phase 5 build plan). Placeholder now so the response shape is
    # stable; adding real data later is a one-line change here, not a
    # response-shape change downstream.
    dimensions.append({
        'key': 'barcode_confirmation',
        'label': 'Barcode-confirmed products',
        'percentage': None,
    })

    return dimensions


def _data_health_score(dimensions):
    """Equal-weighted average of every dimension with a real percentage.
    Returns None (not 0) if nothing is scored yet — a brand-new business
    with an empty catalog has no meaningful score, not a bad one."""
    scored = [d['percentage'] for d in dimensions if d['percentage'] is not None]
    if not scored:
        return None
    return round(sum(scored) / len(scored), 1)


def _data_health_reason(dimension):
    """Plain-language reason for the worst-scoring dimension — see
    Phase B's triage design: always name the single highest-leverage
    fix, never a pile of alerts at once."""
    key = dimension['key']
    if key == 'cost_price':
        return MESSAGES['DATA_HEALTH_REASON_COST_PRICE'].format(count=dimension['_missing_count'])
    if key == 'taxonomy_depth':
        return MESSAGES['DATA_HEALTH_REASON_TAXONOMY_DEPTH'].format(percentage=dimension['percentage'])
    if key == 'reconciliation':
        unresolved = dimension['_freeform_count'] - dimension['_reconciled_count']
        return MESSAGES['DATA_HEALTH_REASON_RECONCILIATION'].format(count=unresolved)
    return ''


# Absolute-count thresholds for the two "cheap-win" alerts (reconciliation
# backlog, cost-price gap). These exist alongside the percentage-based
# worst-dimension pick above because percentage alone can hide a real
# backlog: 15% of a 300-product catalog missing a cost price is 45
# products — a genuinely actionable pile, even if 85% coverage looks
# fine on the score. When a dimension crosses its raw-count threshold it
# takes priority over the percentage pick; between two dimensions that
# both cross threshold, the larger raw count wins — still exactly one
# nudge surfaced, never a list.
RECONCILIATION_BACKLOG_ALERT_THRESHOLD = 5
COST_PRICE_GAP_ALERT_THRESHOLD = 10


def _raw_action_count(dimension):
    """Raw actionable count for dimensions that have one — used for the
    count-based alert override, independent of the dimension's
    percentage."""
    if dimension['key'] == 'cost_price':
        return dimension.get('_missing_count')
    if dimension['key'] == 'reconciliation':
        return dimension['_freeform_count'] - dimension['_reconciled_count']
    return None


def _pick_worst_dimension(dimensions):
    """
    Single-nudge selection: an absolute-count alert (reconciliation
    backlog, cost-price gap) wins over the percentage-based pick whenever
    one crosses its threshold, since a large raw backlog is actionable
    regardless of how it looks as a ratio. Falls back to the
    lowest-percentage dimension below 100% otherwise. Returns None when
    there's genuinely nothing worth surfacing.
    """
    scored_dims = [d for d in dimensions if d['percentage'] is not None]

    threshold_by_key = {
        'reconciliation': RECONCILIATION_BACKLOG_ALERT_THRESHOLD,
        'cost_price': COST_PRICE_GAP_ALERT_THRESHOLD,
    }
    over_threshold = []
    for d in scored_dims:
        count = _raw_action_count(d)
        threshold = threshold_by_key.get(d['key'])
        if count is not None and threshold is not None and count >= threshold:
            over_threshold.append((count, d))
    if over_threshold:
        over_threshold.sort(key=lambda pair: pair[0], reverse=True)
        return over_threshold[0][1]

    below_max = [d for d in scored_dims if d['percentage'] < 100]
    return min(below_max, key=lambda d: d['percentage']) if below_max else None


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def data_health(request):
    """
    GET /api/v1/reports/data-health/
    One score (0-100, or null if there's not enough data yet to mean
    anything) plus a per-dimension breakdown and the single worst
    dimension to fix next — never a pile of simultaneous alerts.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    dimensions = _data_health_dimensions(business)
    score = _data_health_score(dimensions)

    # Only surface a nudge when there's genuinely something to fix — a
    # dimension sitting at 100% has nothing left to improve, and a
    # "worst dimension" reason that reads "0 products are missing a cost
    # price" is noise, not a nudge. Matches the "never show an alert with
    # nothing behind it" intent, not just "always name the lowest number."
    # An absolute-count backlog (reconciliation queue, cost-price gap)
    # can also take priority here — see _pick_worst_dimension.
    worst = _pick_worst_dimension(dimensions)
    worst_out = None
    if worst:
        worst_out = {
            'key': worst['key'],
            'label': worst['label'],
            'percentage': worst['percentage'],
            'reason': _data_health_reason(worst),
            'action_count': _raw_action_count(worst),
        }

    # Strip internal bookkeeping fields (prefixed `_`) before returning —
    # they exist only to compute reasons above, not for the API response.
    clean_dimensions = [
        {k: v for k, v in d.items() if not k.startswith('_')}
        for d in dimensions
    ]

    return Response({
        'score': score,
        'dimensions': clean_dimensions,
        'worst_dimension': worst_out,
    })


# ── Milestones (Phase 5) ─────────────────────────────────────────────────────
# Celebratory events, computed and stored lazily by apps.reports.services at
# the call sites where they can actually fire (sale creation, reconciliation
# resolve, cost-price writes) — this endpoint is read-only, just returns
# what's already been recorded. Most-recent-first, capped at a handful since
# the frontend only ever needs to know about recent ones to decide whether
# to show a toast (dismissal/seen-state is a frontend concern, not tracked
# here — see Phase 5 build plan).

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired, IsOwnerOrManager])
def milestones(request):
    """
    GET /api/v1/reports/milestones/
    The business's most recent milestones (highest single-day sales,
    first fully-reconciled week, cost-price coverage crossing 80%),
    newest first.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    LIMIT = 10
    qs = BusinessMilestone.objects.filter(business=business).order_by('-achieved_at')[:LIMIT]
    return Response(BusinessMilestoneSerializer(qs, many=True).data)