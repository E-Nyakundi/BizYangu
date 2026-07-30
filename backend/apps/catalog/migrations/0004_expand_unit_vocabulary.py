"""
Expand Product.unit from the old 7-value generic vocabulary to the full
25-value taxonomy vocabulary from knowledge/units.json.

Previously, taxonomy-driven onboarding (Phase 4) mapped the taxonomy's
richer unit vocabulary down to whichever of 7 generic values was
closest — e.g. 'sack_50kg' and 'gorogoro' both collapsed to 'kg',
'debe_20l' collapsed to 'l'. That was a deliberate choice to avoid a
bigger migration at the time (see the mapping table this replaces in
apps.knowledge's old taxonomyUnitToProductUnit). On reflection, the
taxonomy's unit list was chosen deliberately to reflect how goods are
actually sold in Kenyan SME contexts (by the sack, by the debe, by the
gorogoro) — collapsing that back down to generic buckets throws away
real information a business owner cares about. This migration adopts
the taxonomy's vocabulary as the single source of truth instead.

`choices` is Django/DRF-level validation only — Postgres has no CHECK
constraint on this column, so the AlterField below doesn't touch the
database schema at all. The RunPython step is what actually matters:
converting the four old values that don't already have an identical
match in the new vocabulary. 'kg', 'g', and 'ml' are untouched since
they're spelled identically in both.
"""

from django.db import migrations, models


OLD_TO_NEW = {
    'pcs': 'piece',
    'l': 'litre',
    'pack': 'packet',
    'box': 'crate',
}


def migrate_units_forward(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    for old_value, new_value in OLD_TO_NEW.items():
        Product.objects.filter(unit=old_value).update(unit=new_value)


def migrate_units_backward(apps, schema_editor):
    # Best-effort reverse: only the four values that had a direct old-side
    # equivalent can be restored. Anything created using one of the other
    # 21 new-only units (bag, bale, dozen, gorogoro, service, ...) has no
    # equivalent to roll back to and is left as-is — those didn't exist
    # as choices before this migration, so there's nothing meaningful to
    # revert them to.
    Product = apps.get_model('catalog', 'Product')
    for old_value, new_value in OLD_TO_NEW.items():
        Product.objects.filter(unit=new_value).update(unit=old_value)


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_phase9_11_taxonomy_expiry'),
    ]

    operations = [
        migrations.RunPython(migrate_units_forward, migrate_units_backward),
        migrations.AlterField(
            model_name='product',
            name='unit',
            field=models.CharField(
                max_length=10,
                choices=[
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
                    ('debe_20l', 'Debe (20L tin)'),
                    ('gorogoro', 'Gorogoro (~2kg tin measure)'),
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
                ],
                default='piece',
            ),
        ),
    ]
