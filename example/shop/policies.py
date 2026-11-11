"""
A rule no permission can say: nobody edits an order once it is delivered.

Everything else - view, create, approve, print an invoice - is decided by the
permission and its scope, with no code.
"""

from clearance.policies import BasePolicy
from clearance.registry import registry
from shop.models import Order


class OrderPolicy(BasePolicy):
    model = Order
    codename = 'order'

    def can_edit(self, user, obj=None):
        if not self.has_within_scope(user, 'edit', obj):
            return False
        return obj is None or obj.status != Order.Status.DELIVERED


order_access = registry.register(OrderPolicy)
