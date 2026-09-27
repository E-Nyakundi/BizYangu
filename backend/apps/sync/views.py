"""
BizYangu — offline sync views (Phase 5, Build Plan v3 Tier 2).

Thin HTTP layer, same convention as every other app here — the actual
logic lives in services.py.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsNotExpired
from apps.core.messages import MESSAGES
from . import services


def get_business_or_404(request):
    business = request.user.business
    if not business:
        return None, Response({'detail': MESSAGES['SYNC_BUSINESS_REQUIRED']}, status=status.HTTP_404_NOT_FOUND)
    return business, None


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsNotExpired])
def pull(request):
    """
    GET /api/v1/sync/pull/?since=<ISO8601 timestamp, or omit for first sync>

    Returns every syncable model's changes since `since`, scoped to the
    caller's business. `since` applies to every model in the same
    request — a device tracks one cursor per model locally (see each
    model's `_sync_timestamp` in the response) and should pass the
    OLDEST of its per-model cursors here, accepting that models further
    ahead will return some rows it already has. Re-applying an
    already-applied row is expected to be a safe no-op on the device
    (upsert by id), not an error.

    Response shape:
        {
          "products": {"rows": [...], "reached_page_limit": false},
          "product_units": {"rows": [...], "reached_page_limit": false},
          "transactions": {...},
          "stock_movements": {...},
          "repackage_events": {...},
          "customers": {...},
          "customer_payments": {...}
        }

    Each row includes a `_sync_timestamp` field — the device should
    store the max `_sync_timestamp` it received per model as that
    model's new cursor. When `reached_page_limit` is true for a model,
    the device should re-pull immediately using that model's own new
    cursor before considering itself caught up — there may be more
    rows waiting past the page it just received.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    since_param = request.query_params.get('since')
    try:
        since = services.parse_since(since_param)
    except ValueError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    result = {}
    for model_name in services.PULL_MODELS:
        rows, reached_page_limit = services.pull_changes(business, model_name, since, request=request)
        result[model_name] = {'rows': rows, 'reached_page_limit': reached_page_limit}

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsNotExpired])
def push(request):
    """
    POST /api/v1/sync/push/
    Body: {"operations": [{"client_id": "<device-local id>", "type": "create_sale", "payload": {...}}, ...]}

    Applies every operation and returns a per-operation result — this
    endpoint never fails a whole batch for one bad record. See
    services.apply_push_operation() for the exact result shape and the
    rationale (this is the direct fix for the Vontran bug named in the
    build plan: a previous SyncEngine never read per-record errors and
    retried permanently-rejected records forever — that failure mode is
    structurally impossible here because there is no whole-batch
    success/failure to misread in the first place).

    `client_id` is opaque to the server except for operations that
    support idempotent retry (currently: create_sale), where it doubles
    as the dedup key — see apps.transactions.services.record_sale's
    sync_idempotency_key parameter. This is the direct fix for the
    Vontran retry bug: a device that resends the same create_sale
    operation with the same client_id after never receiving the first
    response gets back the original sale, not a duplicate. This
    requires the device to generate client_id once per queued write and
    reuse it unchanged across retries — a fresh client_id per retry
    attempt defeats the dedup.
    """
    business, err = get_business_or_404(request)
    if err:
        return err

    operations = request.data.get('operations')
    if not isinstance(operations, list) or not operations:
        return Response(
            {'detail': MESSAGES['VALIDATION_ERROR']},
            status=status.HTTP_400_BAD_REQUEST,
        )

    results = [
        services.apply_push_operation(business, request.user, op)
        for op in operations
    ]

    return Response({'results': results})
