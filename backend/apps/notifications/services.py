"""
BizYangu — push notification service.

Sends FCM (Firebase Cloud Messaging) pushes using the HTTP v1 API.
Currently used for one thing: low-stock / out-of-stock alerts when a
product's stock crosses its threshold.

Design notes:
- This is intentionally fail-soft. If Firebase isn't configured yet
  (no service account on this laptop), we log a warning and return —
  we never want a missing push credential to break a sale or stock
  movement. The write operation that triggered the notification has
  already committed by the time this runs.
- Runs synchronously for now (no Celery wiring yet in this prototype's
  process list). If push volume becomes a problem, wrap
  `notify_low_stock` in a Celery task — the function signature doesn't
  need to change, just the call site.
- google-auth handles the OAuth2 service-account flow under the hood.
  Legacy FCM server-key auth was deprecated by Google in 2024, so v1
  is the only supported path going forward.
"""

import json
import logging
import time

import requests
from django.conf import settings

from apps.core.messages import MESSAGES

logger = logging.getLogger(__name__)

_FCM_SEND_URL_TEMPLATE = 'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'

# Cached (token, expires_at_epoch) tuple so we don't mint a new OAuth2
# token on every single push — they're valid for ~1 hour.
_token_cache = {'access_token': None, 'expires_at': 0}


def _get_access_token():
    """
    Returns a valid OAuth2 access token for the FCM service account,
    or None if push isn't configured / credentials are invalid.
    """
    now = time.time()
    if _token_cache['access_token'] and now < _token_cache['expires_at'] - 60:
        return _token_cache['access_token']

    raw_creds = getattr(settings, 'FCM_SERVICE_ACCOUNT_JSON', '')
    if not raw_creds:
        logger.info('FCM_SERVICE_ACCOUNT_JSON not configured — push notifications disabled.')
        return None

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GoogleAuthRequest

        info = json.loads(raw_creds)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/firebase.messaging'],
        )
        credentials.refresh(GoogleAuthRequest())
        _token_cache['access_token'] = credentials.token
        _token_cache['expires_at'] = credentials.expiry.timestamp() if credentials.expiry else now + 3000
        return credentials.token
    except Exception:
        logger.exception('Failed to obtain FCM access token.')
        return None


def _project_id():
    raw_creds = getattr(settings, 'FCM_SERVICE_ACCOUNT_JSON', '')
    if not raw_creds:
        return None
    try:
        return json.loads(raw_creds).get('project_id')
    except Exception:
        return None


def send_push_to_token(token: str, title: str, body: str, data: dict | None = None) -> bool:
    """
    Send a single push message to one device token via FCM HTTP v1.
    Returns True on success, False otherwise. Never raises.
    """
    access_token = _get_access_token()
    project_id = _project_id()
    if not access_token or not project_id:
        return False

    payload = {
        'message': {
            'token': token,
            'notification': {'title': title, 'body': body},
            'data': {k: str(v) for k, v in (data or {}).items()},
            'android': {'priority': 'HIGH'},
        }
    }

    try:
        resp = requests.post(
            _FCM_SEND_URL_TEMPLATE.format(project_id=project_id),
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json; UTF-8',
            },
            json=payload,
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.warning('FCM push failed (%s): %s', resp.status_code, resp.text[:300])
        return False
    except requests.RequestException:
        logger.exception('FCM push request errored.')
        return False


def notify_low_stock(product, status: str) -> None:
    """
    Notify every active device on `product.business` that a product has
    crossed into LOW or OUT status. Logs the attempt either way via
    NotificationLog so the owner can see in Django admin whether a push
    was even attempted (useful before Firebase is fully configured).

    `status` should be 'LOW' or 'OUT' — the status *after* the change
    that triggered this call.
    """
    from .models import DeviceToken, NotificationLog

    if status not in ('LOW', 'OUT'):
        return

    kind = NotificationLog.Kind.OUT_OF_STOCK if status == 'OUT' else NotificationLog.Kind.LOW_STOCK
    title = MESSAGES['OUT_OF_STOCK_TITLE'] if status == 'OUT' else MESSAGES['LOW_STOCK_TITLE']
    body = (
        MESSAGES['OUT_OF_STOCK_BODY'].format(product=product.name)
        if status == 'OUT' else
        MESSAGES['LOW_STOCK_BODY'].format(
            product=product.name,
            stock=product.current_stock,
            unit=product.unit,
            threshold=product.low_stock_threshold,
        )
    )

    tokens = list(
        DeviceToken.objects.filter(business=product.business, is_active=True).values_list('token', flat=True)
    )

    sent_ok = False
    error = ''
    if not tokens:
        error = 'Hakuna kifaa kilichosajiliwa kupokea arifa.'
    else:
        results = [
            send_push_to_token(t, title, body, data={'product_id': str(product.id), 'kind': kind})
            for t in tokens
        ]
        sent_ok = any(results)
        if not sent_ok:
            error = 'Push haikutumwa — angalia FCM_SERVICE_ACCOUNT_JSON au token zilizosajiliwa.'

    try:
        NotificationLog.objects.create(
            business=product.business,
            product=product,
            kind=kind,
            title=title,
            body=body,
            recipients_count=len(tokens),
            sent_successfully=sent_ok,
            error=error,
        )
    except Exception:
        # Logging the attempt is best-effort — never let it raise.
        logger.exception('Failed to write NotificationLog for low-stock alert.')
