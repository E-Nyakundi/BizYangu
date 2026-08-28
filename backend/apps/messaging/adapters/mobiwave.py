"""
BizYangu — MobiWave SMS adapter (Phase 6.5).

*** NOT PRODUCTION READY — SEE BELOW ***

Unlike the Africa's Talking adapter, this one is NOT extracted from a
working integration. As of this phase, BizYangu has only seen MobiWave's
public pricing page (https://mobiwave.co.ke/pricing) — real, dated, with
confirmed tiered rates — but no confirmed API documentation: no endpoint
URL, no request/response shape, no authentication mechanism, no
confirmed Sender ID processing timeline.

Everything below marked TODO is a guess at a conventional REST/JSON shape
(the kind most Kenyan bulk-SMS resellers use), written so the rest of the
codebase (NotificationService, the priority-list config, delivery
logging) can be built and tested against this adapter's interface
*today*, without waiting on MobiWave's docs. Do not point this at
MobiWave's real API and expect it to work — get their actual docs first
(ask specifically for: endpoint URL, auth method, request/response JSON
shape, and whether Sender ID has the same "1 week + authorisation
letter" requirement their shortcode products list, since the pricing
page doesn't say either way for Sender ID).

Once real docs exist, update this file's request-building and
response-parsing logic to match — the DeliveryResult contract at the
bottom (success/provider_name/provider_message_id/error) should not need
to change.
"""

import logging

from django.conf import settings

from apps.messaging.base import SMSProviderAdapter, DeliveryResult

logger = logging.getLogger(__name__)

# TODO: confirm real endpoint from MobiWave's API docs — this is a guess.
MOBIWAVE_SEND_URL = 'https://api.mobiwave.co.ke/v1/sms/send'


class MobiWaveAdapter(SMSProviderAdapter):
    provider_name = 'mobiwave'

    def send(self, phone_number: str, message: str) -> DeliveryResult:
        api_key = getattr(settings, 'MOBIWAVE_API_KEY', '')
        sender_id = getattr(settings, 'MOBIWAVE_SENDER_ID', '') or None

        if not api_key:
            # Mirrors the "no credentials configured" shape the other
            # adapter's caller used to check for — but as a normal
            # DeliveryResult failure rather than special-cased here, so
            # NotificationService's fallback logic (see service.py)
            # handles a not-yet-configured provider the same way it
            # handles any other failure: skip to the next one.
            return DeliveryResult(
                success=False,
                provider_name=self.provider_name,
                error='MOBIWAVE_API_KEY not configured',
            )

        try:
            import requests  # already a dependency (requirements/base.txt)

            # TODO: confirm real request shape — this is a guess at a
            # conventional REST/JSON body, not verified against MobiWave's
            # actual API.
            payload = {
                'to': phone_number,
                'message': message,
                'sender_id': sender_id,
            }
            headers = {'Authorization': f'Bearer {api_key}'}

            response = requests.post(
                MOBIWAVE_SEND_URL, json=payload, headers=headers, timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            logger.info('[MobiWave] sent to %s: %s', phone_number, data)

            # TODO: confirm the real response shape's success indicator
            # and message-ID field name — guessing at plausible names.
            return DeliveryResult(
                success=True,
                provider_name=self.provider_name,
                provider_message_id=data.get('message_id'),
            )
        except Exception as exc:
            logger.error('[MobiWave] send failed for %s: %s', phone_number, exc)
            return DeliveryResult(
                success=False,
                provider_name=self.provider_name,
                error=str(exc),
            )
