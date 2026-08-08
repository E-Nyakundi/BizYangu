"""
BizYangu — field-level encryption for per-business M-Pesa credentials.

Businesses' own Daraja consumer_secret/passkey now live in our
database (see models.BusinessMpesaCredentials) instead of only in
server env vars. That's real money-moving API credentials for
potentially hundreds of businesses sitting in one table — a plain
CharField would mean a single DB leak (backup, dump, misconfigured
read replica) exposes every business's M-Pesa app secret at once.
This encrypts those specific fields at rest with Fernet (symmetric,
authenticated encryption), keyed by a dedicated secret that is NOT
SECRET_KEY, so rotating one never breaks the other.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet() -> Fernet:
    key = getattr(settings, 'MPESA_CREDENTIALS_ENCRYPTION_KEY', '')
    if not key:
        raise ImproperlyConfigured(
            'MPESA_CREDENTIALS_ENCRYPTION_KEY is not set — required to store/read '
            'per-business M-Pesa credentials. Generate one with: '
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedCharField(models.CharField):
    """
    Transparently encrypts on save, decrypts on load. Stores
    ciphertext (base64, always longer than the plaintext) so
    max_length should be generous — see BusinessMpesaCredentials
    for the sizes used here.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == '':
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Wrong/rotated key, or pre-encryption plaintext leftover
            # in a dev DB — fail loudly rather than silently
            # returning ciphertext as if it were a usable secret.
            raise ImproperlyConfigured(
                'Could not decrypt an encrypted M-Pesa credential field — '
                'MPESA_CREDENTIALS_ENCRYPTION_KEY may be wrong or rotated '
                'without re-encrypting existing rows.'
            )
