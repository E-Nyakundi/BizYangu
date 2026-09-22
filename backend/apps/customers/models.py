"""
BizYangu — customer models (Build Plan v3, Phase 12).

Decision (open question in the build plan, resolved here): yes, a new
Customer model is needed. Before this, CREDIT was just a payment_method
tag on Transaction with no identity attached — there was no way to answer
"who owes what," which is the entire point of Phase 12. Kept deliberately
light per the plan's framing ("not necessarily a full user account"): a
customer is a name + optional phone the owner can look up and bill later,
not a login, not a User row, not linked to accounts.User at all.

Balance is never stored — it's computed on read from CREDIT sales minus
refunds against those sales minus recorded payments (see services.py).
Storing a running balance field would just be a second source of truth to
keep in sync with Transaction/CustomerPayment history; computing it is
cheap at this data scale and can never drift out of sync by construction.
"""

import uuid
from django.db import models
from django.conf import settings


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=200)
    # Optional on purpose — a regular's name may be all the owner has at
    # first; phone can be filled in later. Uniqueness (when provided) is
    # enforced at the serializer level, not a DB constraint, because a DB
    # unique_together on a nullable/blank field would reject a second
    # customer with no phone recorded at all.
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Phase 5 (offline sync) — Customer is a genuinely mutable record
    # (name/phone/notes/is_active can all be edited after creation),
    # unlike CustomerPayment which is append-only. A pull-sync keyed on
    # "changed since timestamp X" needs this to notice an edited
    # customer, not just a newly-created one. Column already exists in
    # the database via migration 0002_customer_updated_at — this
    # declaration was missing from the model despite that, which broke
    # CustomerSerializer (lists 'updated_at' in Meta.fields) and
    # apps.sync.services.PULL_MODELS['customers'] (filters/orders on
    # it) with a FieldError. Restored to match 0002 exactly.
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CustomerPayment(models.Model):
    """
    A payment the customer made against their running CREDIT balance.
    Amount-only, deliberately mirroring the refund flow's design (Build
    Plan v3 Phase 12 item 13: "mirror the existing partial-refund-style
    amount-based UX") — the owner types one KES number, nothing about
    which sale(s) it pays down. It's applied against the customer's total
    balance, not itemized per-sale, the same way a refund amount is
    apportioned internally rather than asked of the user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('business.Business', on_delete=models.PROTECT, related_name='customer_payments')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='customer_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer.name}: KES {self.amount}'
