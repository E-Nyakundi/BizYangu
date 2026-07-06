"""
BizYangu — register the C2B confirmation/validation URLs with Safaricom.

Daraja does not persist these across tunnel-domain changes. Re-run this
every time the Cloudflare/ngrok tunnel domain rotates, or C2B
confirmations have nowhere to land.

Usage:
    python manage.py register_c2b
    python manage.py register_c2b --response-type Cancelled
"""

from django.core.management.base import BaseCommand, CommandError

from apps.payments.daraja import DarajaError, register_c2b_urls


class Command(BaseCommand):
    help = 'Registers the M-Pesa C2B confirmation/validation URLs with Safaricom Daraja.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--response-type',
            default='Completed',
            choices=['Completed', 'Cancelled'],
            help="Safaricom's fallback behaviour if ValidationURL is unreachable (default: Completed).",
        )

    def handle(self, *args, **options):
        try:
            result = register_c2b_urls(response_type=options['response_type'])
        except DarajaError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS('C2B URLs registered with Safaricom.'))
        self.stdout.write(str(result))
