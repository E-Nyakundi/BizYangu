"""
BizYangu — reports services.

Milestone-checking functions, called lazily from the call sites where the
underlying data actually changes (sale creation, reconciliation resolve,
product cost-price writes) — see Phase 5 build plan, design note #3.
Deliberately self-contained (no imports from apps.transactions.views or
apps.catalog.views) so those view modules can import this one without a
circular-import problem.

Every check function is cheap (a handful of aggregate queries scoped to
one business) and idempotent — calling one twice in the same state is a
no-op, so callers don't need to reason about "did this already fire."
"""

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import BusinessMilestone


def _today_net_sales(business, today):
    """Net revenue (gross SALE - REFUND) for a single calendar date,
    scoped to one business. Deliberately independent of
    apps.reports.views._money_summary to avoid importing that module
    here — see the module docstring."""
    from apps.transactions.models import Transaction

    gross = Transaction.objects.filter(
        business=business, type=Transaction.Type.SALE, is_voided=False,
        created_at__date=today,
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    refunded = Transaction.objects.filter(
        business=business, type=Transaction.Type.REFUND, is_voided=False,
        created_at__date=today,
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    return gross - refunded


def check_highest_day_sales_milestone(business, today=None):
    """
    Fires (and re-fires, updating the stored value) whenever today's net
    sales beat every previous day on record. Idempotent per calendar day:
    multiple sales on the same record-breaking day update one row rather
    than creating duplicates.
    """
    today = today or timezone.localdate()
    today_net = _today_net_sales(business, today)
    if today_net <= 0:
        return None

    best = (
        BusinessMilestone.objects
        .filter(business=business, milestone_type=BusinessMilestone.MilestoneType.HIGHEST_DAY_SALES)
        .exclude(achieved_at__date=today)
        .order_by('-value')
        .first()
    )
    best_value = best.value if best else Decimal('0.00')
    if today_net <= best_value:
        return None

    existing_today = BusinessMilestone.objects.filter(
        business=business,
        milestone_type=BusinessMilestone.MilestoneType.HIGHEST_DAY_SALES,
        achieved_at__date=today,
    ).first()
    if existing_today:
        if today_net > existing_today.value:
            existing_today.value = today_net
            existing_today.save(update_fields=['value'])
        return existing_today

    return BusinessMilestone.objects.create(
        business=business,
        milestone_type=BusinessMilestone.MilestoneType.HIGHEST_DAY_SALES,
        value=today_net,
        achieved_at=timezone.now(),
    )


def check_fully_reconciled_week_milestone(business):
    """
    Fires once, the first time the business has a full trailing week with
    every freeform (not-in-catalog) sale item resolved: the reconciliation
    queue is currently empty, nothing sold in the last 7 days is still
    outstanding, and there's actually at least 7 days of history to judge
    (a 2-day-old business hasn't earned this yet, it just hasn't had time
    to accumulate a backlog). No daily snapshots are kept, so this is a
    trailing-week check at read time rather than a literal day-by-day
    replay — the cheap, honest version described in the Phase 5 plan.
    """
    from apps.transactions.models import Transaction, TransactionItem

    already = BusinessMilestone.objects.filter(
        business=business, milestone_type=BusinessMilestone.MilestoneType.FULLY_RECONCILED_WEEK,
    ).exists()
    if already:
        return None

    earliest_sale = (
        Transaction.objects.filter(business=business, type=Transaction.Type.SALE)
        .order_by('created_at').first()
    )
    if not earliest_sale:
        return None

    week_ago = timezone.now() - timezone.timedelta(days=7)
    if earliest_sale.created_at > week_ago:
        return None

    still_open = TransactionItem.objects.filter(
        transaction__business=business, product__isnull=True, is_reconciled=False,
    ).exists()
    if still_open:
        return None

    return BusinessMilestone.objects.create(
        business=business,
        milestone_type=BusinessMilestone.MilestoneType.FULLY_RECONCILED_WEEK,
        achieved_at=timezone.now(),
    )


def check_confidence_to_act_milestone(business):
    """
    Fires once, the first time cost-price coverage across the active
    catalog crosses ~80% — the point at which the profit/margin reports
    stop being a rough guess. Mirrors the cost_price dimension already
    computed in apps.reports.views._data_health_dimensions.
    """
    from apps.catalog.models import Product

    already = BusinessMilestone.objects.filter(
        business=business, milestone_type=BusinessMilestone.MilestoneType.CONFIDENCE_TO_ACT,
    ).exists()
    if already:
        return None

    products = Product.objects.filter(business=business, is_active=True)
    total = products.count()
    if not total:
        return None

    with_cost = products.exclude(cost_price__isnull=True).count()
    percentage = round(with_cost / total * 100, 1)
    if percentage < 80:
        return None

    return BusinessMilestone.objects.create(
        business=business,
        milestone_type=BusinessMilestone.MilestoneType.CONFIDENCE_TO_ACT,
        value=Decimal(str(percentage)),
        achieved_at=timezone.now(),
    )


def check_sale_milestones(business):
    """Convenience wrapper for the sale-creation call site — the two
    milestone types a completed sale can possibly move."""
    check_highest_day_sales_milestone(business)
    check_fully_reconciled_week_milestone(business)


def check_catalog_milestones(business):
    """Convenience wrapper for any call site that writes cost_price or
    resolves a reconciliation item — the two milestone types catalog/
    reconciliation changes can possibly move."""
    check_confidence_to_act_milestone(business)
    check_fully_reconciled_week_milestone(business)
