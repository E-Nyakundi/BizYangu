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
    class Unit(models.TextChoices):
        # These values must match frontend/app/(app)/stock/page.tsx's
        # UNIT_OPTIONS exactly — that's the only place a unit gets chosen,
        # and DRF validates 'unit' against this list. A prior mismatch here
        # (backend had 'piece'/'litre'/'custom', frontend sent 'pcs'/'l'/
        # 'g'/'ml'/'box') meant only 'kg' and 'pack' ever actually worked;
        # every other unit button silently 400'd on product creation.
        PIECE = 'pcs', 'Pieces'
        KG = 'kg', 'Kilogram'
        GRAM = 'g', 'Gram'
        LITRE = 'l', 'Litre'
        MILLILITRE = 'ml', 'Millilitre'
        PACK = 'pack', 'Pack'
        BOX = 'box', 'Box'

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
