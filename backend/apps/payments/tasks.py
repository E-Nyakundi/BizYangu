"""
BizYangu — payments periodic tasks.

Autodiscovered by Celery via `app.autodiscover_tasks()` in
bizyangu/celery.py — no manual registration needed beyond
CELERY_BEAT_SCHEDULE in settings/base.py.

Requires celery beat running alongside the regular worker, e.g.:
    celery -A bizyangu worker -l info
    celery -A bizyangu beat -l info
(or `celery -A bizyangu worker -B -l info` to run both in one process
for local dev — not recommended for production).
"""

import logging

from celery import shared_task

from .services import void_stale_pending_stk_requests

logger = logging.getLogger(__name__)


@shared_task
def check_stale_stk_requests():
    """
    Periodic sweep (see CELERY_BEAT_SCHEDULE): finds any M-Pesa STK Push
    still PENDING past STK_TIMEOUT_MINUTES with no Daraja callback ever
    received, and auto-voids the underlying sale, restoring stock.

    This is the fix for the gap flagged in CHANGES.md — previously the
    only way out of a stuck PENDING sale was the owner/manager manually
    voiding it from Transaction History. This task closes that gap
    automatically; the manual void path stays available as a fallback.
    """
    count = void_stale_pending_stk_requests()
    if count:
        logger.info('STK timeout sweep: voided %s stale pending sale(s)', count)
    return count
