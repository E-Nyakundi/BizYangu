# Generated for BizYangu pre-pilot item D13 — split payment reconciliation.

from django.db import migrations, models


def backfill_split_amounts(apps, schema_editor):
    """
    Existing rows predate this column split — every historical transaction
    was single-method (MIXED wasn't actually tracked as a real split, see
    item D13), so this is a lossless backfill: whichever payment_method
    the row already has, its full total_amount goes into the matching
    column. MIXED rows (if any exist) have no way to recover their real
    split retroactively — they're left at 0/0/0, same as before this
    migration, rather than guessing.
    """
    Transaction = apps.get_model('transactions', 'Transaction')
    Transaction.objects.filter(payment_method='CASH').update(cash_amount=models.F('total_amount'))
    Transaction.objects.filter(payment_method='MPESA').update(mpesa_amount=models.F('total_amount'))
    Transaction.objects.filter(payment_method='CREDIT').update(credit_amount=models.F('total_amount'))


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0005_transaction_customer'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='cash_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='transaction',
            name='mpesa_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='transaction',
            name='credit_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(backfill_split_amounts, migrations.RunPython.noop),
    ]
