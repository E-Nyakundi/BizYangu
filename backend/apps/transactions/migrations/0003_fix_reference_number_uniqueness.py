"""
Fix reference_number uniqueness: it was global (unique=True on the field
alone), but _generate_reference() in models.py has always generated it
scoped per business (each business's BY-YYYY-NNNN counter starts at 0001).
That mismatch meant any business's first-ever sale would collide with
another business's BY-2026-0001 the moment it also existed.

This migration drops the global unique constraint and adds a per-business
one instead: (business, reference_number) unique together.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0002_add_refund_links'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='reference_number',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                fields=('business', 'reference_number'),
                name='unique_business_reference_number',
            ),
        ),
    ]
