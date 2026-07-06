"""
BizYangu — reports WebSocket consumer.

One group per business: `dashboard_business_{business_id}`. Mirrors the
pattern in apps/payments/consumers.py (MPesaConsumer) — see the Phase 5
handoff notes.

Deliberately thin: this does NOT push full report payloads over the
socket. It pushes a small 'dashboard.tick' event whenever something
that changes the numbers happens (a sale, refund, void, or stock
movement), and the frontend refetches GET /reports/dashboard/ in
response. Computing the aggregate here too would mean keeping two
copies of the same business logic in sync (Python here, plus
reports/views.py's _money_summary etc.) — cheaper and less bug-prone
to have the socket just say "something changed, go re-ask the REST
endpoint" than to duplicate the aggregation.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        business_id = self.scope['url_route']['kwargs']['business_id']

        if not user or not user.is_authenticated or str(getattr(user, 'business_id', '')) != str(business_id):
            await self.close(code=4401)
            return

        self.group_name = f'dashboard_business_{business_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def dashboard_tick(self, event):
        """Handler name must match the 'type' key sent in group_send: 'dashboard.tick' -> dashboard_tick."""
        await self.send(text_data=json.dumps(event['payload']))


def notify_dashboard(business_id, reason: str) -> None:
    """
    Call this after anything that changes today's numbers: a sale,
    refund, void, or stock movement. Fails silently if Channels/Redis
    isn't reachable — same tradeoff as payments._broadcast: a dropped
    tick just means the dashboard updates on next manual refresh
    instead of live, it never breaks the write that triggered it.

    `reason` is a short machine tag (e.g. 'sale', 'refund', 'void',
    'stock_movement') — purely informational, lets the frontend log/
    debug what triggered a given tick without the socket needing to
    carry a full payload.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from django.utils import timezone

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            f'dashboard_business_{business_id}',
            {'type': 'dashboard.tick', 'payload': {'reason': reason, 'at': timezone.now().isoformat()}},
        )
    except Exception:
        logger.exception('Dashboard WebSocket broadcast failed for business %s', business_id)
