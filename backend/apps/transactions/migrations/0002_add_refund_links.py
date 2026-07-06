# Generated for BizYangu — adds refund linkage fields.
# Session: standalone refund endpoint (Phase 4 wrap-up, ahead of Phase 5).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='original_transaction',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='refunds', to='transactions.transaction',
            ),
        ),
        migrations.AddField(
            model_name='transactionitem',
            name='original_item',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='refund_items', to='transactions.transactionitem',
            ),
        ),
    ]
