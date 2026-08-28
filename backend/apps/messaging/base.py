"""
BizYangu — messaging provider interface (Phase 6.5).

Every SMS provider (Africa's Talking, MobiWave, and whatever comes next)
implements SMSProviderAdapter. Nothing outside this app should ever import
a vendor SDK (africastalking, requests-to-mobiwave, etc) directly —
apps/accounts and anywhere else that needs to send an OTP or alert goes
through NotificationService in service.py, which is the only thing that
knows the provider priority list and how to fail over between them.

Why a dataclass return instead of a bare bool:
send_otp_sms() used to just return True/False. That was enough when there
was one provider — either it worked or it didn't, and the caller didn't
need to know more. With multiple providers and failover, the caller (or
at least the delivery log) needs to know WHICH provider actually
succeeded/failed and why, or comparing AT vs MobiWave on real delivery
data (the whole point of this phase) is impossible.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DeliveryResult:
    """
    Outcome of a single send attempt against a single provider.

    success: did the provider accept/deliver the message. For providers
        that only confirm submission (not final delivery), this means
        "the provider's API accepted it" — that distinction matters if a
        future provider adds delivery-report webhooks, but isn't
        available for AT or MobiWave today, so it isn't modeled here yet.
    provider_name: short identifier ('africastalking', 'mobiwave') —
        used for logging/comparison, not shown to end users.
    provider_message_id: the provider's own ID for this send, if it gave
        one. Useful for support/debugging ("AT says message X was sent,
        why didn't the phone get it") but optional — not every provider
        API returns one, and its absence is never itself a failure.
    error: human-readable failure reason, for logs only. None on success.
    """
    success: bool
    provider_name: str
    provider_message_id: Optional[str] = None
    error: Optional[str] = None


class SMSProviderAdapter:
    """
    Contract every SMS provider adapter implements. Deliberately tiny —
    routing, failover, and logging all live in NotificationService, once,
    not duplicated per adapter. An adapter's only job is: try to send,
    report back honestly what happened. It must never raise — every
    failure mode (network error, bad credentials, provider 500, timeout)
    gets caught inside send() and turned into a DeliveryResult with
    success=False, so NotificationService can always try the next
    provider in the priority list without needing a try/except of its
    own around every adapter call.
    """

    #: Must be overridden by subclasses — matches the string used in
    #: SMS_PROVIDER_PRIORITY (see service.py) and in delivery logs.
    provider_name: str = 'unset'

    def send(self, phone_number: str, message: str) -> DeliveryResult:
        raise NotImplementedError
