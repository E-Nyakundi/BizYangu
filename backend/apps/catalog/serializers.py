"""
BizYangu — catalog serializers.
Products and categories.
"""

import csv
import io
from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from apps.core.messages import MESSAGES
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'is_active']
        read_only_fields = ['id']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    stock_status = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'barcode',
            'selling_price', 'cost_price',
            'unit', 'current_stock', 'low_stock_threshold',
            'track_stock', 'image', 'is_active',
            'category', 'category_name',
            'stock_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'sku', 'stock_status', 'created_at', 'updated_at', 'category_name']

    def validate_selling_price(self, value):
        if value <= 0:
            raise serializers.ValidationError(MESSAGES['INVALID_PRICE'])
        return value

    def validate_current_stock(self, value):
        if value < 0:
            raise serializers.ValidationError(MESSAGES['STOCK_CANNOT_BE_NEGATIVE'])
        return value


class ProductCreateSerializer(ProductSerializer):
    """Used for creation — business is injected from the view."""

    def create(self, validated_data):
        return Product.objects.create(**validated_data)


class CSVImportResultSerializer(serializers.Serializer):
    """Response for bulk CSV import."""
    imported = serializers.IntegerField()
    skipped = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField())


# ── CSV import helper ────────────────────────────────────────────────────────

REQUIRED_CSV_COLS = {'name', 'selling_price'}
OPTIONAL_CSV_COLS = {
    'category', 'cost_price', 'unit', 'current_stock',
    'low_stock_threshold', 'barcode', 'track_stock',
}


def parse_product_csv(file_obj, business) -> dict:
    """
    Parse a CSV file and bulk-create products for the given business.
    Returns {'imported': N, 'skipped': N, 'errors': [...]}.
    """
    text = file_obj.read().decode('utf-8-sig')  # utf-8-sig handles Excel BOM
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return {'imported': 0, 'skipped': 0, 'errors': [{'row': 0, 'error': 'Faili tupu au muundo mbaya.'}]}

    headers = {h.strip().lower() for h in reader.fieldnames}
    missing = REQUIRED_CSV_COLS - headers
    if missing:
        return {
            'imported': 0,
            'skipped': 0,
            'errors': [{'row': 0, 'error': f'Safu zinazohitajika hazipo: {", ".join(missing)}'}],
        }

    imported = 0
    skipped = 0
    errors = []
    category_cache = {}

    for i, row in enumerate(reader, start=2):  # row 1 is header
        row = {k.strip().lower(): v.strip() for k, v in row.items()}
        name = row.get('name', '').strip()
        if not name:
            skipped += 1
            continue

        try:
            selling_price = Decimal(row.get('selling_price', '0').replace(',', ''))
            if selling_price <= 0:
                raise ValueError(MESSAGES['INVALID_PRICE'])
        except (InvalidOperation, ValueError) as e:
            errors.append({'row': i, 'field': 'selling_price', 'error': str(e)})
            skipped += 1
            continue

        # Resolve or create category
        cat_name = row.get('category', '').strip()
        category = None
        if cat_name:
            if cat_name not in category_cache:
                cat, _ = Category.objects.get_or_create(business=business, name=cat_name)
                category_cache[cat_name] = cat
            category = category_cache[cat_name]

        cost_price = None
        if row.get('cost_price'):
            try:
                cost_price = Decimal(row['cost_price'].replace(',', ''))
            except InvalidOperation:
                pass

        try:
            current_stock = Decimal(row.get('current_stock', '0').replace(',', ''))
        except InvalidOperation:
            current_stock = Decimal('0')

        try:
            low_stock_threshold = Decimal(row.get('low_stock_threshold', '5').replace(',', ''))
        except InvalidOperation:
            low_stock_threshold = Decimal('5')

        unit = row.get('unit', Product.Unit.PIECE)
        if unit not in dict(Product.Unit.choices):
            unit = Product.Unit.PIECE

        track_stock_raw = row.get('track_stock', 'true').lower()
        track_stock = track_stock_raw not in ('false', '0', 'no', 'hapana')

        Product.objects.create(
            business=business,
            name=name,
            selling_price=selling_price,
            cost_price=cost_price,
            current_stock=current_stock,
            low_stock_threshold=low_stock_threshold,
            unit=unit,
            track_stock=track_stock,
            barcode=row.get('barcode', ''),
            category=category,
        )
        imported += 1

    return {'imported': imported, 'skipped': skipped, 'errors': errors}