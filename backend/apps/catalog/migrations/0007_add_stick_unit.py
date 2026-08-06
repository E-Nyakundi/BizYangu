"""
Adds 'stick' to the unit vocabulary.

This was referenced only in comments (pack/stick as the canonical example
of a shared-pool repackaged unit) but never actually added as a choice on
either Product.unit or ProductUnit.unit — so creating a ProductUnit with
unit='stick' 400'd at the DRF ChoiceField validation step, before ever
reaching the repackage/ratio logic. This migration closes that gap.

No data migration needed — no existing rows use 'stick' since it never
validated successfully before now.
"""

from django.db import migrations, models


UNIT_CHOICES = [
    ('piece', 'Piece'),
    ('kg', 'Kilogram'),
    ('g', 'Gram'),
    ('litre', 'Litre'),
    ('ml', 'Millilitre'),
    ('bottle', 'Bottle'),
    ('crate', 'Crate'),
    ('can', 'Can'),
    ('packet', 'Packet'),
    ('bag', 'Bag'),
    ('bale', 'Bale'),
    ('sack_50kg', '50kg sack/bag'),
    ('tonne', 'Tonne'),
    ('gorogoro', 'Gorogoro (standard tin measure)'),
    ('stick', 'Stick'),
    ('dozen', 'Dozen'),
    ('roll', 'Roll'),
    ('metre', 'Metre (length)'),
    ('foot', 'Foot (length)'),
    ('pair', 'Pair'),
    ('set', 'Set'),
    ('bucket', 'Bucket (paint)'),
    ('gauge', 'Gauge (roofing sheet thickness)'),
    ('service', 'Per service (no unit — service businesses)'),
    ('session', 'Per session (service businesses)'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_alter_product_unit_productunit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='unit',
            field=models.CharField(choices=UNIT_CHOICES, default='piece', max_length=10),
        ),
        migrations.AlterField(
            model_name='productunit',
            name='unit',
            field=models.CharField(choices=UNIT_CHOICES, max_length=10),
        ),
    ]
