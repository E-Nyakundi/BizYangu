"""
BizYangu — catalog models.
Products and categories.
"""

import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
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
        # 'debe_20l' removed (migration 0006) — "debe" isn't a standard
        # size the way gorogoro is; it varies by container and was
        # baking in a false 20L assumption. Litre/Millilitre cover this
        # case correctly instead — see ProductUnit below.
        # GOROGORO's label deliberately carries no weight: a gorogoro is
        # a standard *volume* measure, not a standard weight — 2kg only
        # ever held for maize specifically, at that density. A gorogoro
        # of beans or omena weighs something else entirely from the same
        # volume. The actual weight-per-gorogoro for a given product is
        # captured on ProductUnit.ratio_to_parent, never assumed here.
        GOROGORO = 'gorogoro', 'Gorogoro (standard tin measure)'
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


# True unit-of-measure facts — always the same ratio regardless of what
# product they're attached to. Litre:ml is always 1000 no matter whether
# it's cooking oil or paraffin; kg:g is always 1000 no matter the
# product. These are safe to pre-fill on ProductUnit.ratio_to_parent.
#
# Deliberately NOT included: anything container/packaging-based
# (gorogoro:kg, bag:piece, pack:stick, sack_50kg:kg). Those vary by
# product — a gorogoro of maize and a gorogoro of omena hold different
# weights at the same volume — so there is no correct default; the
# owner must enter the real number for that specific product.
#
# Keyed as frozenset({parent_unit, child_unit}) -> ratio (units of
# child per 1 unit of parent), since the pair is unordered for lookup
# purposes but the stored ratio always means "parent -> child".
FIXED_UNIT_RATIOS = {
    frozenset({Product.Unit.LITRE, Product.Unit.MILLILITRE}): Decimal('1000'),
    frozenset({Product.Unit.KG, Product.Unit.GRAM}): Decimal('1000'),
    frozenset({Product.Unit.DOZEN, Product.Unit.PIECE}): Decimal('12'),
}


def get_fixed_ratio(parent_unit, child_unit):
    """
    Returns the known ratio (units of child per 1 unit of parent) for a
    true unit-of-measure pair, or None if this pair has no fixed
    conversion and must be entered by the owner (e.g. gorogoro, pack,
    bag — anything container/packaging-based).
    """
    return FIXED_UNIT_RATIOS.get(frozenset({parent_unit, child_unit}))


class ProductUnit(models.Model):
    """
    One sellable/stockable physical form of a Product. Forms a tree per
    product via `parent` — the root node (parent=None) is the unit the
    product is restocked in.

    Every non-root node is either:
      - is_repackaged=False: shares the same physical stock pool as its
        parent, with quantity computed on the fly via ratio_to_parent —
        e.g. a cigarette pack and its sticks. No loss, no event, exact
        conversion. Nothing to log; opening a pack isn't a real-world
        action worth recording.
      - is_repackaged=True: has its own separately-tracked
        stock_quantity, which only increases via an explicit
        RepackageEvent (see apps.inventory.models) — e.g. a 90kg bag
        turned into gorogoro tins of maize. This is a real physical
        act that can produce less than the theoretical yield (loss),
        so it's logged rather than assumed.

    ratio_to_parent always means "how many of this unit make up one
    unit of the parent" and is always empirical/product-specific unless
    the (parent.unit, self.unit) pair is a true unit-of-measure fact —
    see get_fixed_ratio() above, used only to pre-fill a default in the
    API/serializer layer, never enforced here.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='units')
    unit = models.CharField(max_length=10, choices=Product.Unit.choices)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children',
    )
    ratio_to_parent = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True,
        help_text='How many of this unit make up one unit of the parent. Null only for the root unit.',
    )
    is_repackaged = models.BooleanField(
        default=False,
        help_text='True if turning the parent into this unit is a real, loggable physical act (see RepackageEvent). '
                   'False if this unit shares the same stock pool as its parent (e.g. pack/stick).',
    )
    stock_quantity = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        help_text='Only meaningful for the root unit or is_repackaged=True units. '
                   'Ignored for shared-pool units — their availability is computed, not stored.',
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Price for this specific sellable form. A stick is not simply 1/20th of the pack price.',
    )
    is_sellable = models.BooleanField(default=True)
    is_root = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product', 'created_at']
        constraints = [
            # A root unit represents the restock form itself — it can't
            # also be the *result* of repackaging something else, and it
            # has no parent to compute a ratio against.
            models.CheckConstraint(
                check=~models.Q(is_root=True, is_repackaged=True),
                name='catalog_productunit_root_not_repackaged',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.get_unit_display()}'

    def clean(self):
        if self.is_root:
            if self.parent_id is not None:
                raise ValidationError('Root unit cannot have a parent.')
            if self.ratio_to_parent is not None:
                raise ValidationError('Root unit cannot have a ratio_to_parent.')
            if self.is_repackaged:
                raise ValidationError('Root unit cannot be marked is_repackaged.')
        else:
            if self.parent_id is None:
                raise ValidationError('Non-root units must have a parent.')
            if self.ratio_to_parent is None:
                raise ValidationError('Non-root units must have a ratio_to_parent.')
            if self.parent_id and self.parent.product_id != self.product_id:
                raise ValidationError('parent must belong to the same product.')

    def _walk_to_counted_ancestor(self):
        """
        Returns (counted_node, accumulated_ratio) where counted_node is
        the nearest ancestor (possibly self) that has its own
        stock_quantity counter, and accumulated_ratio is how many units
        of self equal one unit of counted_node.
        """
        if self.is_root or self.is_repackaged:
            return self, Decimal('1')
        ratio = self.ratio_to_parent
        node = self.parent
        while node and not (node.is_root or node.is_repackaged):
            ratio *= node.ratio_to_parent
            node = node.parent
        if node is None:
            # Shouldn't happen — the root is always counted — but fail
            # loudly rather than silently returning a wrong number.
            raise ValidationError(f'{self} has no counted ancestor in its chain.')
        return node, ratio

    def available_quantity(self):
        """Quantity of this specific unit currently sellable."""
        counted_node, ratio = self._walk_to_counted_ancestor()
        if counted_node is self:
            return self.stock_quantity
        return counted_node.stock_quantity * ratio

    def deduct_sale(self, quantity):
        """
        Records a sale of `quantity` of this unit by decrementing
        whichever ancestor actually holds the counter for this pool.
        Caller is responsible for wrapping this in the same atomic
        block as the rest of the sale and for not calling this with
        quantity > available_quantity().
        """
        counted_node, ratio = self._walk_to_counted_ancestor()
        if counted_node is self:
            counted_node.stock_quantity -= quantity
        else:
            counted_node.stock_quantity -= (quantity / ratio)
        counted_node.save(update_fields=['stock_quantity', 'updated_at'])
