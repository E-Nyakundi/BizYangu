"""
BizYangu — Safaricom Daraja API client.

Thin wrapper around the three Daraja calls this app needs:
  1. OAuth token  (Consumer Key/Secret -> Bearer token, cached ~50 min)
  2. STK Push     (Lipa na M-Pesa Online — prompts the customer's phone)
  3. STK Query    (poll a CheckoutRequestID if the callback never arrives)

Sandbox vs production base URL is controlled by MPESA_ENV in settings
('sandbox' default, 'production' to go live). Everything here raises
DarajaError on failure — callers decide how to handle it (the view
layer turns that into a clean Kiswahili error message for the cashier).
"""

import base64
import time
from datetime import datetime

import requests
from django.conf import settings

SANDBOX_BASE_URL = 'https://sandbox.safaricom.co.ke'
PRODUCTION_BASE_URL = 'https://api.safaricom.co.ke'

_token_cache = {'access_token': None, 'expires_at': 0}


class DarajaError(Exception):
    pass


def _base_url() -> str:
    env = getattr(settings, 'MPESA_ENV', 'sandbox')
    return PRODUCTION_BASE_URL if env == 'production' else SANDBOX_BASE_URL


def get_access_token() -> str:
    """
    Returns a cached OAuth2 access token, fetching a new one if expired
    or not yet cached. Daraja tokens are valid for 3600s; we refresh a
    minute early to avoid edge-of-expiry failures.
    """
    now = time.time()
    if _token_cache['access_token'] and now < _token_cache['expires_at'] - 60:
        return _token_cache['access_token']

    key = settings.MPESA_CONSUMER_KEY
    secret = settings.MPESA_CONSUMER_SECRET
    if not key or not secret:
        raise DarajaError('MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET hazijawekwa.')

    try:
        resp = requests.get(
            f'{_base_url()}/oauth/v1/generate?grant_type=client_credentials',
            auth=(key, secret),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data['access_token']
        expires_in = int(data.get('expires_in', 3599))
        _token_cache['access_token'] = token
        _token_cache['expires_at'] = now + expires_in
        return token
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise DarajaError(f'Imeshindikana kupata token ya Daraja: {exc}') from exc


def _password_and_timestamp() -> tuple[str, str]:
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    shortcode = settings.MPESA_SHORTCODE
    passkey = settings.MPESA_PASSKEY
    raw = f'{shortcode}{passkey}{timestamp}'
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


def stk_push(*, phone_number: str, amount, account_reference: str, transaction_desc: str) -> dict:
    """
    Initiates Lipa na M-Pesa Online (STK Push). Returns the raw Daraja
    response dict on success — callers pull MerchantRequestID /
    CheckoutRequestID off it. Raises DarajaError on any failure
    (network, bad credentials, or Daraja returning a non-zero
    ResponseCode).
    """
    token = get_access_token()
    password, timestamp = _password_and_timestamp()
    shortcode = settings.MPESA_SHORTCODE
    callback_url = settings.MPESA_CALLBACK_URL

    if not callback_url:
        raise DarajaError('MPESA_CALLBACK_URL haijawekwa — Safaricom haitajua pa kutuma majibu.')

    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
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
            f'{_base_url()}/mpesa/stkpush/v1/processrequest',
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


def stk_query(*, checkout_request_id: str) -> dict:
    """
    Polls Daraja for the result of a previously-initiated STK push.
    Useful as a fallback when the callback webhook never fires (e.g.
    ngrok tunnel dropped mid-transaction).
    """
    token = get_access_token()
    password, timestamp = _password_and_timestamp()
    shortcode = settings.MPESA_SHORTCODE

    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id,
    }
    try:
        resp = requests.post(
            f'{_base_url()}/mpesa/stkpushquery/v1/query',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=20,
        )
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise DarajaError(f'Ukaguzi wa STK Push umeshindikana: {exc}') from exc


def _c2b_urls_from_callback() -> tuple[str, str]:
    """
    Derives the C2B confirmation/validation URLs from MPESA_CALLBACK_URL
    so there's a single source of truth for the tunnel domain — the
    same value that already gets updated whenever the Cloudflare
    tunnel rotates. Falls back to explicit settings if provided.
    """
    confirmation = getattr(settings, 'MPESA_C2B_CONFIRMATION_URL', '') or ''
    validation = getattr(settings, 'MPESA_C2B_VALIDATION_URL', '') or ''
    if confirmation and validation:
        return confirmation, validation

    callback_url = settings.MPESA_CALLBACK_URL
    if not callback_url:
        raise DarajaError('MPESA_CALLBACK_URL haijawekwa — haiwezekani kujenga URL za C2B.')

    base = callback_url.rsplit('/mpesa/callback', 1)[0].rstrip('/')
    return f'{base}/mpesa/c2b/confirmation/', f'{base}/mpesa/c2b/validation/'


def register_c2b_urls(*, response_type: str = 'Completed') -> dict:
    """
    Registers the C2B confirmation/validation URLs with Safaricom
    (POST /mpesa/c2b/v1/registerurl). Daraja does not persist these —
    every time the tunnel domain rotates (ngrok/Cloudflare), this must
    be re-run, or C2B confirmations silently have nowhere to land.

    response_type: 'Completed' (Safaricom completes the transaction
    even if ValidationURL is unreachable) or 'Cancelled' (Safaricom
    cancels it instead). 'Completed' is the safer default for a duka
    POS — a flaky tunnel shouldn't be able to block a real payment.
    """
    token = get_access_token()
    shortcode = settings.MPESA_SHORTCODE
    confirmation_url, validation_url = _c2b_urls_from_callback()

    payload = {
        'ShortCode': shortcode,
        'ResponseType': response_type,
        'ConfirmationURL': confirmation_url,
        'ValidationURL': validation_url,
    }

    try:
        resp = requests.post(
            f'{_base_url()}/mpesa/c2b/v1/registerurl',
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

