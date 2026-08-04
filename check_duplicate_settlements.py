# Run on the Oracle VM: python manage.py shell < check_duplicate_settlements.py
from apps.customers.models import CustomerPayment

for cid in ['1400c415-d6b9-425a-bb26-74ccc432055c', '36a0f273-d5f4-46bb-9acf-cbe1cd56a304']:
    print(f'--- customer {cid} ---')
    for p in CustomerPayment.objects.filter(customer_id=cid).order_by('created_at'):
        print(p.created_at, 'KES', p.amount, 'by', p.created_by_id, 'notes:', p.notes or '(none)')
