"""
BizYangu — Safaricom Daraja API client.

Thin wrapper around the three Daraja calls this app needs:
  1. OAuth token  (Consumer Key/Secret -> Bearer token, cached ~50 min)
  2. STK Push     (Lipa na M-Pesa Online — prompts the customer's phone)
  3. STK Query    (poll a CheckoutRequestID if the callback never arrives)

Sandbox vs production base URL is controlled per-credential-set (see
MpesaCredentials.env below). Everything here raises DarajaError on
failure — callers decide how to handle it (the view layer turns that
into a clean Kiswahili error message for the cashier).

MULTI-TENANT NOTE: this client is credential-set-based, not settings-
based, on purpose. Two credential sets exist today:
  - default_credentials()  — the shared sales-flow shortcode (env
    MPESA_*), used for business sales until each business gets its
    own Daraja app (planned; see Business.mpesa_* fields).
  - company_credentials()  — BizYangu's own shortcode (env
    MPESA_COMPANY_*), used only for subscription billing.
Every business will eventually get its own MpesaCredentials built
from fields stored on the Business model — that's why nothing below
reads `settings.MPESA_*` directly inside the call functions anymore.
"""

import base64
import time
from dataclasses import dataclass
from datetime import datetime

import requests
from django.conf import settings

SANDBOX_BASE_URL = 'https://sandbox.safaricom.co.ke'
PRODUCTION_BASE_URL = 'https://api.safaricom.co.ke'

# Token cache is keyed by consumer_key so different credential sets
# (sales shortcode vs. company shortcode vs., later, per-business
# shortcodes) never share or clobber each other's cached token.
_token_cache: dict[str, dict] = {}


class DarajaError(Exception):
    pass


@dataclass(frozen=True)
class MpesaCredentials:
    """
    One Daraja app's worth of config. Build one of these per
    "identity" that can receive M-Pesa money — the shared sales
    shortcode, BizYangu's own company shortcode, or a specific
    business's own till/paybill (see business_credentials() below).
    """
    consumer_key: str
    consumer_secret: str
    shortcode: str
    passkey: str
    callback_url: str
    env: str = 'sandbox'
    label: str = 'default'  # for error messages / logging only
    # Daraja needs a different TransactionType for a Buy Goods till
    # vs. a Paybill — this is what the "Buy Goods vs Paybill" decision
    # (doc item 14) actually changes at the API level.
    transaction_type: str = 'CustomerPayBillOnline'

    def base_url(self) -> str:
        return PRODUCTION_BASE_URL if self.env == 'production' else SANDBOX_BASE_URL


def default_credentials() -> MpesaCredentials:
    """The shared sales-flow shortcode every business currently uses."""
    return MpesaCredentials(
        consumer_key=settings.MPESA_CONSUMER_KEY,
        consumer_secret=settings.MPESA_CONSUMER_SECRET,
        shortcode=settings.MPESA_SHORTCODE,
        passkey=settings.MPESA_PASSKEY,
        callback_url=settings.MPESA_CALLBACK_URL,
        env=getattr(settings, 'MPESA_ENV', 'sandbox'),
        label='sales',
    )


def company_credentials() -> MpesaCredentials:
    """BizYangu's own shortcode — subscription billing only."""
    return MpesaCredentials(
        consumer_key=settings.MPESA_COMPANY_CONSUMER_KEY,
        consumer_secret=settings.MPESA_COMPANY_CONSUMER_SECRET,
        shortcode=settings.MPESA_COMPANY_SHORTCODE,
        passkey=settings.MPESA_COMPANY_PASSKEY,
        callback_url=settings.MPESA_COMPANY_CALLBACK_URL,
        env=getattr(settings, 'MPESA_COMPANY_ENV', 'sandbox'),
        label='company',
    )


def business_credentials(business, *, ignore_active: bool = False) -> 'MpesaCredentials | None':
    """
    Builds MpesaCredentials from a business's own configured Daraja
    app (apps.payments.models.BusinessMpesaCredentials), if any.
    Returns None if the business hasn't set one up, or (unless
    ignore_active=True) if it's been disabled — callers should fall
    back to default_credentials() in that case. ignore_active=True is
    for the verify endpoint, which needs to test credentials BEFORE
    flipping is_active on.
    """
    creds = getattr(business, 'mpesa_credentials', None)
    if not creds or (not creds.is_active and not ignore_active):
        return None
    if not creds.is_configured():
        return None

    transaction_type = (
        'CustomerBuyGoodsOnline'
        if creds.till_type == creds.TillType.BUY_GOODS
        else 'CustomerPayBillOnline'
    )
    return MpesaCredentials(
        consumer_key=creds.consumer_key,
        consumer_secret=creds.consumer_secret,
        shortcode=creds.shortcode,
        passkey=creds.passkey,
        callback_url=settings.MPESA_CALLBACK_URL,
        env=creds.env,
        label=f'business:{business.id}',
        transaction_type=transaction_type,
    )


def resolve_sales_credentials(business) -> MpesaCredentials:
    """
    The single place that decides whose shortcode a business's SALE
    (STK Push to their customer) goes through: the business's own
    Daraja app if they've configured and enabled one, otherwise the
    shared sales shortcode every business used before per-business
    tills existed. This is what lets businesses migrate one at a time
    with zero code changes elsewhere.
    """
    return business_credentials(business) or default_credentials()


def get_access_token(credentials: MpesaCredentials) -> str:
    """
    Returns a cached OAuth2 access token for this credential set,
    fetching a new one if expired or not yet cached. Daraja tokens
    are valid for 3600s; we refresh a minute early to avoid
    edge-of-expiry failures.
    """
    cache_key = credentials.consumer_key
    cached = _token_cache.get(cache_key)
    now = time.time()
    if cached and now < cached['expires_at'] - 60:
        return cached['access_token']

    key = credentials.consumer_key
    secret = credentials.consumer_secret
    if not key or not secret:
        raise DarajaError(f'Vitambulisho vya Daraja ({credentials.label}) havijawekwa.')

    try:
        resp = requests.get(
            f'{credentials.base_url()}/oauth/v1/generate?grant_type=client_credentials',
            auth=(key, secret),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data['access_token']
        expires_in = int(data.get('expires_in', 3599))
        _token_cache[cache_key] = {'access_token': token, 'expires_at': now + expires_in}
        return token
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise DarajaError(f'Imeshindikana kupata token ya Daraja ({credentials.label}): {exc}') from exc


def _password_and_timestamp(credentials: MpesaCredentials) -> tuple[str, str]:
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    raw = f'{credentials.shortcode}{credentials.passkey}{timestamp}'
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def normalize_phone(phone: str) -> str:
    """
    Daraja wants 2547XXXXXXXX / 2541XXXXXXXX (no +, no leading 0).
    Accepts the common Kenyan input formats and normalizes them.
    """
    phone = phone.strip().replace(' ', '').replace('-', '')
    if phone.startswith('+'):
        phone = phone[1:]
    if phone.startswith('0') and len(phone) == 10:
        phone = '254' + phone[1:]
    if phone.startswith('7') or phone.startswith('1'):
        phone = '254' + phone
    return phone


def stk_push(
    *, credentials: MpesaCredentials, phone_number: str, amount,
    account_reference: str, transaction_desc: str,
) -> dict:
    """
    Initiates Lipa na M-Pesa Online (STK Push) against the given
    credential set. Returns the raw Daraja response dict on success —
    callers pull MerchantRequestID / CheckoutRequestID off it. Raises
    DarajaError on any failure (network, bad credentials, or Daraja
    returning a non-zero ResponseCode).
    """
    token = get_access_token(credentials)
    password, timestamp = _password_and_timestamp(credentials)
    shortcode = credentials.shortcode
    callback_url = credentials.callback_url

    if not callback_url:
        raise DarajaError(f'CallBackURL ({credentials.label}) haijawekwa — Safaricom haitajua pa kutuma majibu.')

    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': credentials.transaction_type,
        'Amount': int(round(float(amount))),
        'PartyA': normalize_phone(phone_number),
        'PartyB': shortcode,
        'PhoneNumber': normalize_phone(phone_number),
        'CallBackURL': callback_url,
        'AccountReference': account_reference[:12],
        'TransactionDesc': transaction_desc[:13] or 'BizYangu',
    }

    try:
        resp = requests.post(
            f'{credentials.base_url()}/mpesa/stkpush/v1/processrequest',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=20,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise DarajaError(f'Ombi la STK Push limeshindikana: {exc}') from exc

    if str(data.get('ResponseCode')) != '0':
        raise DarajaError(data.get('errorMessage') or data.get('ResponseDescription') or 'STK Push imekataliwa.')

    return data


def stk_query(*, credentials: MpesaCredentials, checkout_request_id: str) -> dict:
    """
    Polls Daraja for the result of a previously-initiated STK push.
    Useful as a fallback when the callback webhook never fires (e.g.
    ngrok tunnel dropped mid-transaction).
    """
    token = get_access_token(credentials)
    password, timestamp = _password_and_timestamp(credentials)

    payload = {
        'BusinessShortCode': credentials.shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id,
    }
    try:
        resp = requests.post(
            f'{credentials.base_url()}/mpesa/stkpushquery/v1/query',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=20,
        )
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise DarajaError(f'Ukaguzi wa STK Push umeshindikana: {exc}') from exc


def _c2b_urls_from_callback(credentials: MpesaCredentials) -> tuple[str, str]:
    """
    Derives the C2B confirmation/validation URLs from the credential
    set's callback_url so there's a single source of truth for the
    tunnel domain — the same value that already gets updated whenever
    the Cloudflare tunnel rotates. Falls back to explicit settings if
    provided (sales credentials only — C2B is a sales-flow concept).
    """
    confirmation = getattr(settings, 'MPESA_C2B_CONFIRMATION_URL', '') or ''
    validation = getattr(settings, 'MPESA_C2B_VALIDATION_URL', '') or ''
    if confirmation and validation:
        return confirmation, validation

    callback_url = credentials.callback_url
    if not callback_url:
        raise DarajaError('CallBackURL haijawekwa — haiwezekani kujenga URL za C2B.')

    base = callback_url.rsplit('/mpesa/callback', 1)[0].rstrip('/')
    return f'{base}/mpesa/c2b/confirmation/', f'{base}/mpesa/c2b/validation/'


def register_c2b_urls(*, credentials: MpesaCredentials | None = None, response_type: str = 'Completed') -> dict:
    """
    Registers the C2B confirmation/validation URLs with Safaricom
    (POST /mpesa/c2b/v1/registerurl). Daraja does not persist these —
    every time the tunnel domain rotates (ngrok/Cloudflare), this must
    be re-run, or C2B confirmations silently have nowhere to land.

    Defaults to the sales credentials — C2B (till-number payments with
    no STK push) is a sales-flow concept, not something the company
    shortcode needs.

    response_type: 'Completed' (Safaricom completes the transaction
    even if ValidationURL is unreachable) or 'Cancelled' (Safaricom
    cancels it instead). 'Completed' is the safer default for a duka
    POS — a flaky tunnel shouldn't be able to block a real payment.
    """
    credentials = credentials or default_credentials()
    token = get_access_token(credentials)
    confirmation_url, validation_url = _c2b_urls_from_callback(credentials)

    payload = {
        'ShortCode': credentials.shortcode,
        'ResponseType': response_type,
        'ConfirmationURL': confirmation_url,
        'ValidationURL': validation_url,
    }

    try:
        resp = requests.post(
            f'{credentials.base_url()}/mpesa/c2b/v1/registerurl',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=20,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise DarajaError(f'Usajili wa C2B URL umeshindikana: {exc}') from exc

    if str(data.get('ResponseCode', data.get('errorCode', ''))) not in ('0', ''):
        raise DarajaError(data.get('errorMessage') or data.get('ResponseDescription') or 'Usajili wa C2B umekataliwa.')

    return data

