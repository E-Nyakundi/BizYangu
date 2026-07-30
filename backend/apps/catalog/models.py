"""
BizYangu — catalog models.
Products and categories.
"""

import uuid
from django.db import models


class Category(models.Model):
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'categories'
        unique_together = [('business', 'name')]

    def __str__(self):
        return self.name


class Product(models.Model):
    class CreationSource(models.TextChoices):
        # Phase 13 (Data Health Score) needs to tell "brand-level" catalog
        # entries apart from generic ones for its taxonomy-depth metric.
        # Once taxonomy onboarding only ever creates brand-level products
        # (Jameson, never "Whisky (various)"), that path is brand-level by
        # construction — there's nothing left to detect there. The real
        # question is everything else: manual/CSV/reconciliation entries
        # can't be reliably classified brand-level vs. generic after the
        # fact by inspecting the name, so provenance is tracked directly
        # at creation instead. Set at all four creation paths — see
        # apps/catalog/views.py, apps/transactions/views.py (reconciliation
        # resolve), and the CSV import path.
        TAXONOMY = 'taxonomy', 'Taxonomy onboarding'
        MANUAL = 'manual', 'Manual entry'
        CSV = 'csv', 'CSV import'
        RECONCILIATION = 'reconciliation', 'Reconciliation resolve'

    class Unit(models.TextChoices):
        # These values must match frontend/app/(app)/stock/page.tsx's
        # UNIT_OPTIONS exactly — that's the only place a unit gets chosen,
        # and DRF validates 'unit' against this list. A prior mismatch here
        # (backend had 'piece'/'litre'/'custom', frontend sent 'pcs'/'l'/
        # 'g'/'ml'/'box') meant only 'kg' and 'pack' ever actually worked;
        # every other unit button silently 400'd on product creation.
        #
        # As of migration 0004, this is the full unit vocabulary from
        # knowledge/units.json — deliberately kept as one source of truth
        # rather than mapping the richer taxonomy vocabulary down to a
        # smaller generic set (see CHANGES.md). IDs and labels below must
        # stay in sync with units.json; if that file gains a unit, this
        # needs a follow-up migration adding it here too.
        PIECE = 'piece', 'Piece'
        KG = 'kg', 'Kilogram'
        GRAM = 'g', 'Gram'
        LITRE = 'litre', 'Litre'
        MILLILITRE = 'ml', 'Millilitre'
        BOTTLE = 'bottle', 'Bottle'
        CRATE = 'crate', 'Crate'
        CAN = 'can', 'Can'
        PACKET = 'packet', 'Packet'
        BAG = 'bag', 'Bag'
        BALE = 'bale', 'Bale'
        SACK_50KG = 'sack_50kg', '50kg sack/bag'
        TONNE = 'tonne', 'Tonne'
        DEBE_20L = 'debe_20l', 'Debe (20L tin)'
        GOROGORO = 'gorogoro', 'Gorogoro (~2kg tin measure)'
        DOZEN = 'dozen', 'Dozen'
        ROLL = 'roll', 'Roll'
        METRE = 'metre', 'Metre (length)'
        FOOT = 'foot', 'Foot (length)'
        PAIR = 'pair', 'Pair'
        SET = 'set', 'Set'
        BUCKET = 'bucket', 'Bucket (paint)'
        GAUGE = 'gauge', 'Gauge (roofing sheet thickness)'
        SERVICE = 'service', 'Per service (no unit — service businesses)'
        SESSION = 'session', 'Per session (service businesses)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PIECE)
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=3, default=5)
    track_stock = models.BooleanField(default=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # Phase 11 (perishability) + Phase 8 taxonomy linkage — added by
    # migration 0003 but missing from this model until now (same gap as
    # Business.taxonomy_type_id: the migration was applied but the model
    # was never updated to match).
    expiry_date = models.DateField(null=True, blank=True)
    taxonomy_brand = models.CharField(max_length=100, blank=True)
    taxonomy_category_id = models.CharField(max_length=100, blank=True)
    taxonomy_subcategory_id = models.CharField(max_length=100, blank=True)
    # Default MANUAL rather than blank — every existing product predates
    # this field and was, in fact, created through some form of manual
    # entry (taxonomy onboarding didn't exist yet when they were made).
    # New code paths must set this explicitly; see CreationSource above.
    created_via = models.CharField(max_length=20, choices=CreationSource.choices, default=CreationSource.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('business', 'sku')]
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.sku:
            import shortuuid
            self.sku = f'BY-{shortuuid.ShortUUID().random(length=6).upper()}'
        super().save(*args, **kwargs)

    @property
    def stock_status(self):
        if self.current_stock <= 0:
            return 'OUT'
        if self.current_stock <= self.low_stock_threshold:
            return 'LOW'
        return 'OK'
