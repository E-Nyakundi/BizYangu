# Generated for BizYangu — fixes Product.unit choices to match what the
# frontend actually sends. See models.py comment on Product.Unit for the
# full story: only 'kg' and 'pack' ever worked before this.

from django.db import migrations, models


def migrate_old_unit_values(apps, schema_editor):
    """Old rows created before this fix may hold 'piece'/'litre'/'custom' —
    translate them to their new equivalents so they don't silently become
    invalid choices."""
    Product = apps.get_model('catalog', 'Product')
    Product.objects.filter(unit='piece').update(unit='pcs')
    Product.objects.filter(unit='litre').update(unit='l')
    Product.objects.filter(unit='custom').update(unit='pcs')


def reverse_unit_values(apps, schema_editor):
    Product = apps.get_model('catalog', 'Product')
    Product.objects.filter(unit='pcs').update(unit='piece')
    Product.objects.filter(unit='l').update(unit='litre')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_old_unit_values, reverse_unit_values),
        migrations.AlterField(
            model_name='product',
            name='unit',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('pcs', 'Pieces'),
                    ('kg', 'Kilogram'),
                    ('g', 'Gram'),
                    ('l', 'Litre'),
                    ('ml', 'Millilitre'),
                    ('pack', 'Pack'),
                    ('box', 'Box'),
                ],
                default='pcs',
            ),
        ),
    ]
