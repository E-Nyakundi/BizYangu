"""
BizYangu — M-Pesa SMS parsing.

Parses the raw text of an M-Pesa confirmation SMS (as read off the
till owner's own phone) into the fields needed to build an
MPesaTransaction row.

Kept in its own module, separate from services.py, because this is
regex/format maintenance, not business logic — a new Safaricom
message-format variant should mean editing this file and nothing
else.

Scope: this module only recognizes and parses "money received"
messages (Buy Goods / Till and Paybill confirmations addressed to the
till/paybill owner). Every other M-Pesa SMS shape a phone might
receive — sent money, cash withdrawal, failed transaction, airtime
purchase, etc. — is explicitly recognized and classified as
not-reconciliation-relevant, never force-parsed into a fake "received"
result. Bank SMS (e.g. Paybill-to-bank settlement) is out of scope
entirely; it isn't Safaricom text and isn't something this module
looks for.

Format variance already confirmed from real samples (see
PHASE_6_SMS_RECONCILIATION_HANDOFF.md):
  - Amounts may or may not have thousands-separator commas
    (Ksh50.00 vs Ksh1,160.00).
  - Phone numbers in "received" messages are partially masked
    (0759***859) — never available as a full MSISDN from SMS text.
  - Date formats differ by era: DD/M/YY (24/3/26) in current-format
    messages, and an older equivalent seen in non-received message
    types. Two-digit years are assumed 20xx.
  - "Confirmed." may or may not be followed by a space before the
    rest of the message.

Only Till and Paybill "received" formats are implemented below, since
those are the two shapes actually sampled this session. Pochi la
Biashara and personal Send Money "received" formats are NOT yet
sampled — see the handoff note "A business's incoming money isn't one
channel" for what's still needed before those can be added here with
any confidence. Until real samples exist for them, an SMS in one of
those shapes will fall through to UNRECOGNIZED rather than be guessed
at.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional


class SmsClassification(str, Enum):
    RECEIVED = 'RECEIVED'          # Till or Paybill payment received — reconciliation-relevant
    SENT = 'SENT'                  # Money sent out (send-money, paybill-out, B2B)
    WITHDRAWAL = 'WITHDRAWAL'      # Cash withdrawal ("Give Ksh... cash to ...")
    FAILED = 'FAILED'              # Failed transaction — no money moved
    UNRECOGNIZED = 'UNRECOGNIZED'  # Doesn't match any known M-Pesa SMS shape at all


@dataclass
class ParsedSms:
    classification: SmsClassification
    # Populated only when classification == RECEIVED. All None otherwise.
    receipt_number: Optional[str] = None
    amount: Optional[Decimal] = None
    transaction_date: Optional[datetime] = None
    phone_number: Optional[str] = None  # may be partially masked, e.g. '0759***859'
    sender_name: Optional[str] = None
    account_reference: Optional[str] = None  # Paybill only; None for Till
    reason: str = ''  # human-readable note, always set — for logging non-RECEIVED cases


_RECEIPT = r'(?P<receipt>[A-Z0-9]{10})'
_AMOUNT = r'Ksh(?P<amount>[\d,]+\.\d{2})'

# "UCOCRAE1RW Confirmed.You have received Ksh50.00 from PETER KAMAU
#  0759***859 on 24/3/26 at 6:52 AM New M-PESA balance is Ksh659.48."
# Till (Buy Goods) — no account reference field.
_TILL_RECEIVED_RE = re.compile(
    rf'^{_RECEIPT}\s+Confirmed\.\s*You have received\s+{_AMOUNT}\s+from\s+'
    rf'(?P<sender>[A-Z][A-Z ]*?)\s+(?P<phone>0\d{{3}}\*{{2,3}}\d{{3}})\s+'
    rf'on\s+(?P<date>\d{{1,2}}/\d{{1,2}}/\d{{2}})\s+at\s+(?P<time>\d{{1,2}}:\d{{2}}\s*[AP]M)',
    re.IGNORECASE,
)

# Paybill "received" shape is NOT yet sampled (see module docstring).
# Best-effort pattern based on Safaricom's well-known public paybill
# wording — kept intentionally close to the Till pattern but with an
# account-reference group. Treat this as provisional until a real
# sample confirms or corrects it; do not assume it's exact.
_PAYBILL_RECEIVED_RE = re.compile(
    rf'^{_RECEIPT}\s+Confirmed\.\s*You have received\s+{_AMOUNT}\s+from\s+'
    rf'(?P<sender>[A-Z][A-Z ]*?)\s+(?P<phone>0\d{{3}}\*{{2,3}}\d{{3}})\s+'
    rf'for account\s+(?P<account>\S+)\s+'
    rf'on\s+(?P<date>\d{{1,2}}/\d{{1,2}}/\d{{2}})\s+at\s+(?P<time>\d{{1,2}}:\d{{2}}\s*[AP]M)',
    re.IGNORECASE,
)

# "JDN4ACB07E Confirmed. Ksh1,160.00 sent to SawaSawa Com Ltd for
#  account XXXXX on 23/4/15 at 6:18 PM New M-PESA balance is Ksh2,779.42."
_SENT_RE = re.compile(r'^[A-Z0-9]{10}\s+Confirmed\.\s*Ksh[\d,]+\.\d{2}\s+sent to\s+', re.IGNORECASE)

# "KJ80WO0XHY Confirmed. On 8/10/16 at 1:43 PM Give Ksh4,000.00 cash
#  to Phonelink Yaya New M-PESA balance is Ksh10,399.00."
_WITHDRAWAL_RE = re.compile(
    r'^[A-Z0-9]{10}\s+Confirmed\.\s*On\s+\d{1,2}/\d{1,2}/\d{2,4}\s+at\s+\d{1,2}:\d{2}\s*[AP]M\s+Give\s+Ksh',
    re.IGNORECASE,
)

# "Failed. Not enough money in your M-PESA account to send Ksh1,000.00. ..."
_FAILED_RE = re.compile(r'^Failed\.', re.IGNORECASE)


def _parse_amount(raw: str) -> Optional[Decimal]:
    try:
        return Decimal(raw.replace(',', ''))
    except (InvalidOperation, AttributeError):
        return None


def _parse_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """
    date_str is DD/M/YY or D/M/YY (two-digit year, assumed 20xx — every
    real sample seen so far, including the 2015/2016-era ones, uses a
    two-digit year). time_str is 'H:MM AM/PM' with possible internal
    whitespace before AM/PM.
    """
    time_str = re.sub(r'\s+', ' ', time_str.strip().upper())
    for date_fmt in ('%d/%m/%y', '%-d/%-m/%y'):
        try:
            combined = f'{date_str.strip()} {time_str}'
            return datetime.strptime(combined, f'{date_fmt} %I:%M %p')
        except ValueError:
            continue
    # Fall back to zero-padding manually if the platform strptime
    # doesn't support %-d/%-m (Windows-style libc).
    try:
        day, month, year = date_str.strip().split('/')
        padded = f'{int(day):02d}/{int(month):02d}/{year}'
        return datetime.strptime(f'{padded} {time_str}', '%d/%m/%y %I:%M %p')
    except (ValueError, AttributeError):
        return None


def parse_mpesa_sms(raw_text: str) -> ParsedSms:
    """
    Classifies and, for RECEIVED messages, fully parses a raw M-Pesa
    SMS string. Never raises on malformed/unexpected input — always
    returns a ParsedSms, falling back to UNRECOGNIZED with a `reason`
    explaining why, so the caller can log it instead of silently
    dropping the SMS or crashing the request.
    """
    text = (raw_text or '').strip()
    if not text:
        return ParsedSms(SmsClassification.UNRECOGNIZED, reason='empty SMS text')

    if _FAILED_RE.match(text):
        return ParsedSms(SmsClassification.FAILED, reason='failed transaction — no money moved')

    if _WITHDRAWAL_RE.match(text):
        return ParsedSms(SmsClassification.WITHDRAWAL, reason='cash withdrawal — not a customer payment')

    if _SENT_RE.match(text):
        return ParsedSms(SmsClassification.SENT, reason='outbound send-money/paybill payment — not a receipt')

    match = _TILL_RECEIVED_RE.match(text)
    channel = 'till'
    if not match:
        match = _PAYBILL_RECEIVED_RE.match(text)
        channel = 'paybill'

    if not match:
        return ParsedSms(
            SmsClassification.UNRECOGNIZED,
            reason=(
                'did not match any known received/sent/withdrawal/failed pattern '
                '(possibly Pochi la Biashara, personal Send Money, a bank SMS, or an '
                'unsampled format variant — see PHASE_6_SMS_RECONCILIATION_HANDOFF.md)'
            ),
        )

    amount = _parse_amount(match.group('amount'))
    if amount is None:
        return ParsedSms(
            SmsClassification.UNRECOGNIZED,
            reason=f'matched a received pattern but amount failed to parse: {match.group("amount")!r}',
        )

    txn_date = _parse_datetime(match.group('date'), match.group('time'))
    if txn_date is None:
        return ParsedSms(
            SmsClassification.UNRECOGNIZED,
            reason=(
                f'matched a received pattern but date/time failed to parse: '
                f'{match.group("date")!r} {match.group("time")!r}'
            ),
        )

    return ParsedSms(
        classification=SmsClassification.RECEIVED,
        receipt_number=match.group('receipt'),
        amount=amount,
        transaction_date=txn_date,
        phone_number=match.group('phone'),
        sender_name=match.group('sender').strip(),
        account_reference=match.groupdict().get('account'),
        reason=f'parsed as {channel} payment received',
    )
