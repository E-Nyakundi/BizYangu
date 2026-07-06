"""
BizYangu — payments WebSocket consumer.

One group per business: `mpesa_business_{business_id}`. The POS
connects once it has a pending M-Pesa sale and listens for any
`mpesa.update` event broadcast by apps/payments/services.py — STK
Push results and C2B auto-matches both flow through here.

Deliberately coarse-grained (whole business, not per-transaction) —
a duka has at most a handful of staff and a handful of pending M-Pesa
sales at once, so the client filtering the stream by transaction_id
itself is simpler than managing one group per in-flight sale.
"""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class MPesaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        business_id = self.scope['url_route']['kwargs']['business_id']

        if not user or not user.is_authenticated or str(getattr(user, 'business_id', '')) != str(business_id):
            await self.close(code=4401)
            return

        self.group_name = f'mpesa_business_{business_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def mpesa_update(self, event):
        """Handler name must match the 'type' key sent in group_send: 'mpesa.update' -> mpesa_update."""
        await self.send(text_data=json.dumps(event['payload']))
