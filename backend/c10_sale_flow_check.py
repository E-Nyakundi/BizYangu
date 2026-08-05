"""
Standalone functional check for the C10 sale-flow integration
(TransactionItem.product_unit + create_sale/create_refund/void_transaction).
Run against the sqlite testing settings, same approach as the earlier
C10 backend/API passes: real APIClient calls against an in-memory DB,
not model-method unit tests.

    SECRET_KEY=x DB_PASSWORD=x DJANGO_SETTINGS_MODULE=bizyangu.settings.testing \
        python3 c10_sale_flow_check.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bizyangu.settings.testing')
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner
from decimal import Decimal
from rest_framework.test import APIClient

runner = DiscoverRunner()
old_config = runner.setup_databases()
setup_test_environment()

checks = []


def check(label, cond):
    checks.append((label, bool(cond)))
    print(('PASS' if cond else 'FAIL'), '-', label)


try:
    from apps.accounts.models import User
    from apps.business.models import Business
    from apps.catalog.models import Product, ProductUnit
    from apps.transactions.models import Transaction, TransactionItem
    from apps.inventory.models import StockMovement

    business = Business.objects.create(
        name='Test Duka', type=Business.Type.DUKA,
        subscription_status=Business.SubscriptionStatus.ACTIVE,
    )
    owner = User.objects.create_user(
        phone_number='+254700000001', name='Owner', password='pass1234',
        role=User.Role.OWNER, business=business,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    # ── Product with a pack/stick tree ──────────────────────────────
    cigs = Product.objects.create(
        business=business, name='Sportsman Cigarettes', selling_price=Decimal('200.00'),
        cost_price=Decimal('150.00'), unit=Product.Unit.PACKET, current_stock=Decimal('0'),
        track_stock=True,
    )
    root = ProductUnit.objects.create(
        product=cigs, unit=Product.Unit.PACKET, is_root=True, is_sellable=False,
        selling_price=None, stock_quantity=Decimal('10'),  # 10 packs
    )
    stick = ProductUnit.objects.create(
        product=cigs, unit=Product.Unit.PIECE, parent=root, ratio_to_parent=Decimal('20'),
        is_repackaged=False, is_sellable=True, selling_price=Decimal('15.00'),
    )

    check('root available_quantity == 10 packs', root.available_quantity() == Decimal('10'))
    check('stick available_quantity == 200 sticks', stick.available_quantity() == Decimal('200'))

    # ── Sell 30 sticks (1.5 packs worth) via product_unit_id ────────
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_unit_id': str(stick.id), 'quantity': '30'}],
        'payment_method': 'CASH',
    }, format='json')
    check('sale via product_unit_id -> 201', resp.status_code == 201)
    txn_id = resp.data.get('id') if resp.status_code == 201 else None

    root.refresh_from_db()
    check('root pool decremented by 1.5 packs (30/20)', root.stock_quantity == Decimal('8.5'))
    check('product.current_stock untouched by unit sale', Product.objects.get(id=cigs.id).current_stock == Decimal('0'))

    item = TransactionItem.objects.get(transaction_id=txn_id)
    check('TransactionItem.product_unit set to the stick unit', item.product_unit_id == stick.id)
    check('TransactionItem.unit_price snapshot == 15.00', item.unit_price == Decimal('15.00'))
    check('TransactionItem.subtotal == 450.00', item.subtotal == Decimal('450.00'))

    mv = StockMovement.objects.filter(transaction_id=txn_id).first()
    check('StockMovement created with product_unit + correct delta', (
        mv is not None and mv.product_unit_id == stick.id
        and mv.quantity_before == Decimal('10') and mv.quantity_after == Decimal('8.5')
        and mv.quantity_change == Decimal('-1.5')
    ))

    # ── Insufficient stock rejection ─────────────────────────────────
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_unit_id': str(stick.id), 'quantity': '999'}],
        'payment_method': 'CASH',
    }, format='json')
    check('over-selling a unit is rejected with 400', resp.status_code == 400)
    root.refresh_from_db()
    check('rejected sale left stock unchanged', root.stock_quantity == Decimal('8.5'))

    # ── Not-sellable unit rejection ──────────────────────────────────
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_unit_id': str(root.id), 'quantity': '1'}],
        'payment_method': 'CASH',
    }, format='json')
    check('selling a non-sellable (root) unit is rejected', resp.status_code == 400)

    # ── No-selling-price rejection ────────────────────────────────────
    no_price_unit = ProductUnit.objects.create(
        product=cigs, unit=Product.Unit.PACKET, parent=root, ratio_to_parent=Decimal('1'),
        is_repackaged=False, is_sellable=True, selling_price=None,
    )
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_unit_id': str(no_price_unit.id), 'quantity': '1'}],
        'payment_method': 'CASH',
    }, format='json')
    check('selling a unit with no selling_price is rejected', resp.status_code == 400)

    # ── Mutually-exclusive shape validation ───────────────────────────
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_unit_id': str(stick.id), 'product_id': str(cigs.id), 'quantity': '1'}],
        'payment_method': 'CASH',
    }, format='json')
    check('product_id + product_unit_id together is rejected', resp.status_code == 400)

    # ── Void restores the unit pool, not Product.current_stock ────────
    resp = client.post(f'/api/v1/transactions/{txn_id}/void/', {'reason': 'test void'}, format='json')
    check('void of a unit-based sale -> 200', resp.status_code == 200)
    root.refresh_from_db()
    check('void restored root pool back to 10', root.stock_quantity == Decimal('10'))
    check('product.current_stock still untouched after void', Product.objects.get(id=cigs.id).current_stock == Decimal('0'))
    void_mv = StockMovement.objects.filter(transaction_id=txn_id, movement_type=StockMovement.MovementType.REFUND).first()
    check('void created a REFUND StockMovement with product_unit set', void_mv is not None and void_mv.product_unit_id == stick.id)

    # ── Refund path (partial) restores the unit pool ───────────────────
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_unit_id': str(stick.id), 'quantity': '40'}],  # 2 packs worth
        'payment_method': 'CASH',
    }, format='json')
    check('second unit sale (40 sticks) -> 201', resp.status_code == 201)
    sale2_id = resp.data['id']
    root.refresh_from_db()
    check('root pool at 8 after second sale (10 - 2)', root.stock_quantity == Decimal('8'))

    resp = client.post('/api/v1/transactions/refund/', {
        'transaction_id': sale2_id, 'amount': '300.00', 'reason': 'test partial refund',
    }, format='json')
    check('partial refund of unit-based sale -> 201', resp.status_code == 201)
    root.refresh_from_db()
    # 300.00 / 15.00 = 20 sticks = 1 pack refunded
    check('root pool restored by 1 pack after refund (8 -> 9)', root.stock_quantity == Decimal('9'))

    # ── Backward compatibility: plain product_id sale unaffected ───────
    plain = Product.objects.create(
        business=business, name='Sugar 1kg', selling_price=Decimal('180.00'),
        cost_price=Decimal('150.00'), unit=Product.Unit.KG, current_stock=Decimal('50'),
        track_stock=True,
    )
    resp = client.post('/api/v1/transactions/sale/', {
        'items': [{'product_id': str(plain.id), 'quantity': '3'}],
        'payment_method': 'CASH',
    }, format='json')
    check('plain product_id sale still works unchanged -> 201', resp.status_code == 201)
    plain.refresh_from_db()
    check('plain product current_stock deducted normally (50 -> 47)', plain.current_stock == Decimal('47'))
    plain_item = TransactionItem.objects.get(transaction_id=resp.data['id'])
    check('plain sale item has product_unit == None', plain_item.product_unit_id is None)

finally:
    teardown_test_environment()
    runner.teardown_databases(old_config)

print()
failed = [label for label, ok in checks if not ok]
print(f'{len(checks) - len(failed)}/{len(checks)} checks passed')
if failed:
    print('FAILED:', failed)
    raise SystemExit(1)
