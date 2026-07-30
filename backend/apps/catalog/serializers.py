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
    # default=None (not just read_only) — without it, DRF omits the key
    # entirely for products with no category (an AttributeError on the
    # category.name source lookup gets silently swallowed) instead of
    # returning null. That's not just cosmetic: frontend grouping code
    # assumes category_name is always present, even if null, and would
    # crash sorting an uncategorized bucket keyed by `undefined` instead
    # of `null`. apps/inventory/serializers.py's equivalent field already
    # has this; this brings ProductSerializer in line with it.
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
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

    # Overrides the read-only category_name inherited from ProductSerializer
    # (which sources from category.name for display only). Here it's a
    # write-only get-or-create hint: pass a category name and the view
    # will find-or-create a Category with that name for this business —
    # the same pattern the CSV import path below already uses. Optional
    # and independent of `category` (a PK): callers that already know a
    # category's id can keep sending that directly; this is for callers
    # (taxonomy-driven onboarding) that only know a category's display
    # name, not any pre-existing id.
    category_name = serializers.CharField(required=False, allow_blank=True, write_only=True)

    # Phase 13 (Data Health) provenance tag — write-only, creation-only
    # (not in ProductSerializer.Meta.fields at all, so it's never
    # touchable via a generic product update). Frontend callers that
    # share this same create endpoint (taxonomy onboarding vs. manual
    # Add Product) are trusted to pass the right value, same trust level
    # as everything else in the creation payload. The reconciliation and
    # CSV import paths set this directly server-side instead of trusting
    # a payload value — see apps/transactions/views.py and the CSV
    # import view below.
    created_via = serializers.ChoiceField(choices=Product.CreationSource.choices, required=False)

    class Meta(ProductSerializer.Meta):
        # created_via is genuinely new here (unlike category_name, which
        # was already in the parent's Meta.fields) — DRF requires every
        # explicitly declared field to also appear in Meta.fields, so this
        # needs its own Meta rather than just inheriting the parent's.
        fields = ProductSerializer.Meta.fields + ['created_via']

    def create(self, validated_data):
        validated_data.pop('category_name', None)  # resolved to `category` in the view, not a model field
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
            created_via=Product.CreationSource.CSV,
        )
        imported += 1

    return {'imported': imported, 'skipped': skipped, 'errors': errors}