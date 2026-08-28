"""
BizYangu — Africa's Talking SMS adapter (Phase 6.5).

Extracted from apps/accounts/services.py's send_otp_sms(), which called
the africastalking SDK directly. Behavior here is intentionally
unchanged from that version — this is a move, not a rewrite:

- Still treats a missing AT_API_KEY as "dev mode, log the code instead of
  sending" rather than a hard failure. That decision now lives in
  NotificationService (see service.py) rather than here, since it's a
  cross-provider concern (any provider missing credentials should behave
  the same way), not something specific to AT.
- Still gated the sandbox-visibility log line on settings.DEBUG, for the
  same reason as before: AT's sandbox environment never delivers to a
  real handset by design, so logging the OTP is the only way to see it
  locally, and this must never fire against a real production settings
  module.
- Still passes sender_id=None (AT's shared default sender) when
  AT_SENDER_ID is blank — unchanged until a real Kenyan Sender ID
  registration exists to put there.
"""

import logging

from django.conf import settings

from apps.messaging.base import SMSProviderAdapter, DeliveryResult

logger = logging.getLogger(__name__)


class AfricasTalkingAdapter(SMSProviderAdapter):
    provider_name = 'africastalking'

    def send(self, phone_number: str, message: str) -> DeliveryResult:
        try:
            import africastalking
            africastalking.initialize(
                username=settings.AT_USERNAME,
                api_key=settings.AT_API_KEY,
            )
            sms = africastalking.SMS
            sender_id = getattr(settings, 'AT_SENDER_ID', '') or None
            response = sms.send(message, [phone_number], sender_id)
            logger.info('[AT] sent to %s: %s', phone_number, response)

            # AT's sandbox environment never delivers to a real handset —
            # by design, not a bug on either side (see AT's own docs).
            # Gated on DEBUG so it can never fire against a real
            # production settings module. This intentionally logs the
            # full response rather than the OTP text itself — the
            # adapter doesn't know or care that this particular message
            # happens to be an OTP; that context lives in the caller.
            if settings.DEBUG:
                logger.warning(
                    '[AT][SANDBOX DEBUG] %s -> %s (AT sandbox never '
                    'reaches a real phone — this log is the only way to '
                    'see delivery locally)', phone_number, response,
                )

            return DeliveryResult(success=True, provider_name=self.provider_name)
        except Exception as exc:
            logger.error('[AT] send failed for %s: %s', phone_number, exc)
            return DeliveryResult(
                success=False,
                provider_name=self.provider_name,
                error=str(exc),
            )
