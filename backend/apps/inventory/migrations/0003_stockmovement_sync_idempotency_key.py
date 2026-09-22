# Phase 5 (offline sync) — lets a retried offline stock-count push be
# safe: without this, a device retrying a push whose response it never
# received would create a duplicate StockMovement every time. Mirrors
# apps/transactions/migrations/0009's identical field on Transaction.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_stockmovement_product_unit_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockmovement',
            name='sync_idempotency_key',
            field=models.CharField(max_length=100, null=True, blank=True, unique=True),
        ),
    ]
