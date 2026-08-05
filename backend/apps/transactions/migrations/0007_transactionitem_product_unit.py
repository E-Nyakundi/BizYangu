# Generated for C10 sale-flow integration (pack-to-unit selling).
#
# Depends explicitly on 0006_transaction_split_payment_amounts — the live
# leaf of the transactions migration chain — not on the stray duplicate
# 0004_transactionitem_is_reconciled_transactionitem_name_and_more found
# alongside 0004_phase9_unreconciled_items in this app (see
# pre-pilot-build-main.md, Carried-over section: that duplicate is a
# known, deliberately untouched issue — run
# `python manage.py showmigrations transactions` against the real DB
# before ever running makemigrations --merge on this app).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_alter_product_unit_productunit'),
        ('transactions', '0006_transaction_split_payment_amounts'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionitem',
            name='product_unit',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transaction_items',
                to='catalog.productunit',
            ),
        ),
    ]
