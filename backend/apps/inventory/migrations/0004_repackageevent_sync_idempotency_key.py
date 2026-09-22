# Phase 5 (offline sync) — lets a retried offline repackage push be
# safe: without this, a device retrying a push whose response it never
# received would create a duplicate RepackageEvent (and double-apply
# the stock movement) every time. Mirrors this app's own 0003 migration
# (StockMovement.sync_idempotency_key) and apps/transactions/0009's
# identical field on Transaction.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_stockmovement_sync_idempotency_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='repackageevent',
            name='sync_idempotency_key',
            field=models.CharField(max_length=100, null=True, blank=True, unique=True),
        ),
    ]
