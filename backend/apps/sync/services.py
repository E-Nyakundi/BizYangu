"""
BizYangu — offline sync services (Phase 5, Build Plan v3 Tier 2).

Two responsibilities:

1. PULL_MODELS describes every model a device can pull "changes since
   timestamp X" for, and how to filter it to one business and order it
   by whatever timestamp field it actually has.

   Not every syncable model has updated_at — only ones that are
   genuinely mutated after creation (Transaction: voiding; Customer:
   editing name/phone/notes/is_active) got updated_at added in this
   phase (migrations apps/transactions/0008, apps/customers/0002).
   Append-only models (TransactionItem, StockMovement, RepackageEvent,
   CustomerPayment) are pulled by created_at instead — a row that's
   never mutated can't be missed by watching only its creation time.

2. apply_push_operation() dispatches one client-submitted write to the
   right handler and returns a per-record result, never raising past
   the caller. This is the direct fix for the named Vontran bug: that
   SyncEngine.push() never read a per-record errors array from the
   response, so rejected records retried forever. There is no way to
   repeat that mistake here, because the wire format has no
   whole-batch success/failure — only a list of per-operation results,
   one per submitted operation, always.
"""

import logging

from django.utils.dateparse import parse_datetime

from apps.catalog.models import Product, ProductUnit
from apps.catalog.serializers import ProductSerializer, ProductUnitSerializer
from apps.core.messages import MESSAGES
from apps.customers.models import Customer, CustomerPayment
from apps.customers.serializers import CustomerSerializer, CustomerPaymentSerializer
from apps.inventory.models import StockMovement, RepackageEvent
from apps.inventory.serializers import StockCountSerializer, StockMovementSerializer, RepackageEventSerializer
from apps.inventory.services import record_stock_count, StockCountError
from apps.transactions.models import Transaction, TransactionItem
from apps.transactions.serializers import SaleCreateSerializer, TransactionSerializer
from apps.transactions.services import record_sale, SaleError

logger = logging.getLogger(__name__)


# Every pullable model: how to scope it to a business, which timestamp
# field marks "changed" for it, and how to serialize each row.
#
# `timestamp_field` drives both the pull filter (>timestamp) and the
# ordering (ascending, so a client that gets cut off partway through a
# huge first pull can resume from the last row it actually saw, rather
# than from "now" and risk missing rows that arrived between the two
# ends of a single unordered page).
PULL_MODELS = {
    'products': {
        'queryset': lambda business: Product.objects.filter(business=business),
        'timestamp_field': 'updated_at',
        'serializer': ProductSerializer,
    },
    'product_units': {
        'queryset': lambda business: ProductUnit.objects.filter(product__business=business),
        'timestamp_field': 'updated_at',
        'serializer': ProductUnitSerializer,
    },
    'transactions': {
        'queryset': lambda business: Transaction.objects.filter(business=business),
        'timestamp_field': 'updated_at',
        'serializer': TransactionSerializer,
    },
    'stock_movements': {
        'queryset': lambda business: StockMovement.objects.filter(business=business),
        # Append-only — see module docstring. created_at is sufficient.
        'timestamp_field': 'created_at',
        'serializer': StockMovementSerializer,
    },
    'repackage_events': {
        'queryset': lambda business: RepackageEvent.objects.filter(business=business),
        'timestamp_field': 'created_at',
        'serializer': RepackageEventSerializer,
    },
    'customers': {
        'queryset': lambda business: Customer.objects.filter(business=business),
        'timestamp_field': 'updated_at',
        'serializer': CustomerSerializer,
    },
    'customer_payments': {
        'queryset': lambda business: CustomerPayment.objects.filter(business=business),
        'timestamp_field': 'created_at',
        'serializer': CustomerPaymentSerializer,
    },
}

# Server-enforced ceiling on rows returned per model per pull request.
# A device with a very stale last-synced timestamp (first sync, or one
# that's been offline for weeks) could otherwise ask for months of sales
# in one response. The client is expected to notice a full page (exactly
# PULL_PAGE_SIZE rows) and immediately re-pull with the last row's own
# timestamp to fetch the next page, same pattern as any cursor-paginated
# API — no separate "next page token" needed since the timestamp itself
# is the cursor.
PULL_PAGE_SIZE = 500


def pull_changes(business, model_name, since):
    """
    Returns (serialized_rows, reached_page_limit) for one model, scoped
    to `business`, changed strictly after `since` (a datetime, or None
    for "everything" — a device's very first sync).

    reached_page_limit is True when exactly PULL_PAGE_SIZE rows came
    back, signalling the client should immediately re-pull this same
    model using the last row's timestamp before considering this
    model caught up.
    """
    spec = PULL_MODELS[model_name]
    qs = spec['queryset'](business)
    ts_field = spec['timestamp_field']

    if since is not None:
        qs = qs.filter(**{f'{ts_field}__gt': since})

    rows = list(qs.order_by(ts_field)[:PULL_PAGE_SIZE])
    reached_page_limit = len(rows) == PULL_PAGE_SIZE

    serializer = spec['serializer']
    data = serializer(rows, many=True).data

    # Echo each row's own timestamp back alongside the serialized fields
    # so the client can advance its per-model cursor to the exact value
    # of the last row it received, not to "now" on the server (which
    # would race against a row written between the query running and
    # the response being read).
    for row, model_instance in zip(data, rows):
        row['_sync_timestamp'] = getattr(model_instance, ts_field).isoformat()

    return data, reached_page_limit


class PushOperationError(Exception):
    """Raised by a push handler for a validation-style failure specific
    to that one operation. Caught by apply_push_operation() and turned
    into that operation's failure entry — never propagates to fail the
    rest of the batch."""
    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


def _push_create_sale(business, user, payload, client_id):
    """
    Handler for push operation type 'create_sale'. Runs the same
    SaleCreateSerializer the live /transactions/sale/ endpoint uses,
    then calls the shared record_sale() service — identical validation
    and stock-deduction behaviour whether the sale was rung up online
    or replayed from an offline queue.

    client_id doubles as the idempotency key passed to record_sale().
    This requires every device to generate a stable, unique client_id
    per queued sale (e.g. a UUID created once, when the sale is first
    recorded offline, and reused unchanged on every retry of that same
    push) — a device that instead generates a fresh client_id on each
    retry attempt defeats the dedup entirely and will get duplicate
    sales, so this is a hard requirement on the client, not optional.
    """
    if not client_id:
        raise PushOperationError(MESSAGES['SYNC_CLIENT_ID_REQUIRED'])

    serializer = SaleCreateSerializer(data=payload)
    if not serializer.is_valid():
        raise PushOperationError(serializer.errors)

    try:
        txn = record_sale(business, user, serializer.validated_data, sync_idempotency_key=client_id)
    except SaleError as e:
        raise PushOperationError(e.detail)

    return TransactionSerializer(txn).data


def _push_create_stock_count(business, user, payload, client_id):
    """
    Handler for push operation type 'create_stock_count' — an offline
    physical stock count/adjustment. Mirrors _push_create_sale's shape
    exactly: same StockCountSerializer the live /inventory/count/
    endpoint uses, same client_id-as-idempotency-key contract, same
    role check duplicated here since there is no DRF permission_classes
    mechanism to lean on for a push operation.

    The role check matters specifically because going offline must
    never become a way to bypass IsOwnerOrManager — a cashier's device
    that's offline still can't push a stock adjustment any more than it
    could submit one live.
    """
    if not client_id:
        raise PushOperationError(MESSAGES['SYNC_CLIENT_ID_REQUIRED'])

    if user.role not in ('OWNER', 'MANAGER'):
        raise PushOperationError(MESSAGES['OWNER_OR_MANAGER_ONLY'])

    serializer = StockCountSerializer(data=payload)
    if not serializer.is_valid():
        raise PushOperationError(serializer.errors)

    try:
        movement = record_stock_count(
            business,
            user,
            serializer.validated_data['product_id'],
            serializer.validated_data['counted_quantity'],
            serializer.validated_data.get('notes', ''),
            sync_idempotency_key=client_id,
        )
    except StockCountError as e:
        raise PushOperationError(e.detail)

    return StockMovementSerializer(movement).data


# Every push operation type this endpoint accepts, mapped to its handler.
# Adding a new syncable write (stock-in, refund, void, customer
# create/edit) is a matter of extracting its logic into a services.py
# function the same way record_sale() and record_stock_count() were
# extracted, then adding one entry here — apply_push_operation() and
# the wire format don't change.
PUSH_HANDLERS = {
    'create_sale': _push_create_sale,
    'create_stock_count': _push_create_stock_count,
}


def apply_push_operation(business, user, operation):
    """
    Applies one client-submitted operation and always returns a result
    dict — never raises. Every result carries back the client's own
    client_id unchanged, so the device can match results to the queued
    writes it's holding regardless of order or whether earlier
    operations in the same batch failed.

    Result shape (always present): {'client_id', 'status'}
      status='ok'    also carries 'server_data' (the created record,
                      serialized) — the device should overwrite its
                      local optimistic copy with this, since server-side
                      values (reference_number, computed totals, a
                      get-or-created customer id) may differ from what
                      the device guessed while offline.
      status='error' also carries 'detail' — a message or field-error
                      dict the device can show the user. An error result
                      means this specific operation was rejected; it is
                      not a reason to retry it unchanged, and it must
                      not block any other operation in the batch from
                      being applied and returned as its own result.
    """
    client_id = operation.get('client_id')
    op_type = operation.get('type')
    payload = operation.get('payload', {})

    handler = PUSH_HANDLERS.get(op_type)
    if handler is None:
        return {
            'client_id': client_id,
            'status': 'error',
            'detail': MESSAGES['SYNC_UNKNOWN_OPERATION_TYPE'].format(op_type=op_type),
        }

    try:
        server_data = handler(business, user, payload, client_id)
    except PushOperationError as e:
        return {'client_id': client_id, 'status': 'error', 'detail': e.detail}
    except Exception:
        # Anything unexpected (a bug, a DB error unrelated to validation)
        # must still come back as this operation's own failure, not a
        # 500 that takes down every other operation queued in the same
        # batch alongside it.
        logger.exception(
            'Unhandled error applying push operation type=%s client_id=%s',
            op_type, client_id,
        )
        return {'client_id': client_id, 'status': 'error', 'detail': MESSAGES['SERVER_ERROR']}

    return {'client_id': client_id, 'status': 'ok', 'server_data': server_data}


def parse_since(value):
    """
    Parses a client-supplied 'since' query param into a datetime, or
    None if absent/empty (meaning "everything" — first sync). Distinct
    from an invalid-format string, which raises ValueError so the view
    can turn it into a 400 rather than silently treating a typo as
    "since the beginning of time" and re-sending a device's entire
    history by accident.
    """
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError(f'Could not parse timestamp: {value!r}')
    return parsed
