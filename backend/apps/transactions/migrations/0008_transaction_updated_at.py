# Phase 5 (offline sync) — Transaction needs updated_at because it's
# mutated after creation (void_transaction sets is_voided/void_reason/
# void_by). Without this, a pull-sync keyed on "changed since timestamp X"
# would miss any transaction that was voided after its original creation
# ever synced to a device — it would look unchanged and never re-pull.
#
# django.utils.timezone.now as the one-time default backfills existing
# rows to "now" at migration time. That's fine: auto_now fields don't
# need historically-accurate values, only a valid starting point, since
# every future save() sets it correctly from here on.

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0007_transactionitem_product_unit'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
