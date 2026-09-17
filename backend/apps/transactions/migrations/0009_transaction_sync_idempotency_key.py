# Phase 5 (offline sync) — lets apps.sync.views.push retry safely. See
# the field's docstring in models.py for the full rationale: without
# this, a device retrying a push whose response it never received would
# create a duplicate sale every time.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0008_transaction_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='sync_idempotency_key',
            field=models.CharField(max_length=100, null=True, blank=True, unique=True),
        ),
    ]
