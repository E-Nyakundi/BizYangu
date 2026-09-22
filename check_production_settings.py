"""
BizYangu — production container startup guard.

Run once, before migrate/daphne, in Dockerfile.prod's CMD. Fails loudly
(non-zero exit, clear message) if this container is somehow about to
serve production traffic with the wrong settings module or DEBUG=True.

Why this exists: DJANGO_SETTINGS_MODULE defaults to
'bizyangu.settings.development' in manage.py, wsgi.py, asgi.py, and
celery.py — standard Django convention, correct for local dev, and
normally overridden by this image's own `ENV DJANGO_SETTINGS_MODULE=
bizyangu.settings.production` in Dockerfile.prod. That override can
still be silently defeated (e.g. a docker-compose `environment:` block
that unsets or overrides it, or this Dockerfile reused as a base for
another service without adjusting it) — this script exists to turn
that failure mode into an immediate container-start crash with a clear
message, instead of a production container quietly serving with
DEBUG=True and no CSRF/CORS enforcement, discovered only after the
fact.
"""
import os
import sys

import django

django.setup()

from django.conf import settings

expected = 'bizyangu.settings.production'
resolved = os.environ.get('DJANGO_SETTINGS_MODULE', '<unset>')

if resolved != expected:
    sys.exit(
        f'Refusing to start: DJANGO_SETTINGS_MODULE={resolved!r}, '
        f'expected {expected!r}. This container is meant to serve '
        f'production traffic and must not fall back to dev settings.'
    )

if settings.DEBUG:
    sys.exit(
        'Refusing to start: DEBUG is True in what should be a '
        'production container.'
    )

print(f'Startup guard OK — running with {resolved}, DEBUG=False.')
