"""
BizYangu — NotificationService (Phase 6.5).

The only thing outside this app should ever call. apps/accounts (and
anywhere else that needs to send an OTP today, or a WhatsApp/email
message in some later phase — see the plan's "Explicitly deferred" list)
imports send_otp() from here, never a vendor SDK or adapter directly.

Routing + failover lives here, once — adapters themselves stay dumb (see
base.py's docstring). Provider priority is config-driven
(SMS_PROVIDER_PRIORITY in settings), not hardcoded, so changing which
provider is primary — or adding a third later — is a settings change,
not a code change here or in apps/accounts.

Dev-mode bypass: if no provider in the priority list has credentials
configured, this logs the OTP instead of failing outright — this
preserves the exact "no AT_API_KEY -> log and return success" behavior
apps/accounts/services.py had before this phase, but as a
provider-agnostic concern (checked once here) rather than something each
adapter would otherwise need to duplicate.
"""

import logging

from django.conf import settings

from apps.messaging.adapters.africastalking import AfricasTalkingAdapter
from apps.messaging.adapters.mobiwave import MobiWaveAdapter
from apps.messaging.models import SMSDeliveryLog

logger = logging.getLogger(__name__)

# Registry of known adapters by the name used in SMS_PROVIDER_PRIORITY.
# Adding a third provider later (e.g. eSMS Africa, per the plan's
# documented-but-not-built candidate) means: write its adapter in
# apps/messaging/adapters/, register it here, add its name to
# SMS_PROVIDER_PRIORITY in settings. Nothing else in this file changes.
_ADAPTER_REGISTRY = {
    'africastalking': AfricasTalkingAdapter,
    'mobiwave': MobiWaveAdapter,
}


def _get_priority_list():
    """
    Reads SMS_PROVIDER_PRIORITY from settings — e.g.
    ['mobiwave', 'africastalking']. Falls back to AT-only if unset, so
    an environment that hasn't added this setting yet behaves exactly
    like before this phase (AT, and only AT).
    """
    return getattr(settings, 'SMS_PROVIDER_PRIORITY', ['africastalking'])


def _any_provider_configured(priority_list) -> bool:
    """
    Mirrors the old "has_credentials" check from services.py, but across
    the whole priority list rather than assuming AT specifically. A
    provider is considered configured if its required setting is
    non-empty — checked the same way each adapter itself checks
    (AT needs AT_API_KEY, MobiWave needs MOBIWAVE_API_KEY).
    """
    credential_settings = {
        'africastalking': 'AT_API_KEY',
        'mobiwave': 'MOBIWAVE_API_KEY',
    }
    return any(
        bool(getattr(settings, credential_settings.get(name, ''), None))
        for name in priority_list
    )


def send_otp(phone_number: str, otp: str, purpose: str = 'otp') -> bool:
    """
    Send a 6-digit OTP, trying each provider in SMS_PROVIDER_PRIORITY in
    order until one succeeds. Returns True/False to match the exact
    signature apps/accounts/views.py already calls — this phase changes
    what happens behind send_otp_sms(), not the call site's contract.

    Every attempt (including ones a later provider then succeeds on) is
    logged to SMSDeliveryLog — that's the point of building this
    in-house rather than trusting a third party's failover (see the
    plan's §3.2): the delivery data is BizYangu's own from day one.
    """
    priority_list = _get_priority_list()
    message = f'Msimbo wako wa BizYangu ni: {otp}. Unaisha baada ya dakika 10.'

    if not _any_provider_configured(priority_list):
        logger.warning(
            '[DEV OTP] %s -> %s (no provider credentials configured, '
            'logging only)', phone_number, otp,
        )
        return True

    last_error = None
    for provider_name in priority_list:
        adapter_cls = _ADAPTER_REGISTRY.get(provider_name)
        if adapter_cls is None:
            logger.error(
                'SMS_PROVIDER_PRIORITY references unknown provider %r — '
                'skipping. Check spelling against _ADAPTER_REGISTRY in '
                'apps/messaging/service.py.', provider_name,
            )
            continue

        result = adapter_cls().send(phone_number, message)

        SMSDeliveryLog.objects.create(
            phone_number=phone_number,
            provider_name=result.provider_name,
            success=result.success,
            provider_message_id=result.provider_message_id or '',
            error=result.error or '',
            purpose=purpose,
        )

        if result.success:
            return True

        last_error = result.error
        logger.warning(
            '[NotificationService] %s failed for %s (%s) — trying next '
            'provider if any remain', provider_name, phone_number, last_error,
        )

    # Every provider in the list failed. Mirror the old fallback
    # behavior (log the OTP for visibility) rather than silently
    # swallowing a login-blocking failure — but return False, since
    # unlike the "no credentials configured" case above, this means
    # providers WERE tried and all genuinely failed; the caller (and
    # ultimately the user) should see this as an error, not a silent
    # success.
    logger.error(
        '[OTP fallback] all configured providers failed for %s — last '
        'error: %s. Logging OTP for visibility: %s -> %s',
        phone_number, last_error, phone_number, otp,
    )
    return False
