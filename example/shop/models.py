"""
A shop: orders placed by customers at one of several branches, managed by
staff - some of whom may see the price.

Nothing here says who may do what. The order declares its permissions, its
protected field and its status action; the bundles and roles that give them
out are in ``config/access.py``.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from clearance.permissions import DEFAULT_ACTIONS, build_permissions
from clearance.querysets import SignedInReadQuerySet
from shop.querysets import OrderQuerySet


class Branch(models.Model):
    """Reference data: anybody signed in may read the branches, to choose one for an order."""

    name = models.CharField(_('name'), max_length=80, unique=True)

    objects = SignedInReadQuerySet.as_manager()

    class Meta:
        verbose_name = _('branch')
        verbose_name_plural = _('branches')

    def __str__(self):
        return self.name


class Person(AbstractUser):
    """Staff and customers alike. A member of staff works at a branch."""

    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('branch')
    )


# --8<-- [start:order]
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        DELIVERED = 'delivered', _('Delivered')

    customer = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='orders', verbose_name=_('customer')
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.PROTECT, related_name='orders', verbose_name=_('branch')
    )
    item = models.CharField(_('item'), max_length=120)
    status = models.CharField(
        _('status'), max_length=16, choices=Status.choices, default=Status.PENDING
    )
    #: Set by the shop, never by the customer - empty until it is.
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2, null=True, blank=True)

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = _('order')
        verbose_name_plural = _('orders')
        default_permissions = ()
        permissions = build_permissions(
            'order',
            _('orders'),
            actions=(*DEFAULT_ACTIONS, 'approve'),
            labels={'approve': _('Can approve or reject %(resource)s')},
            # Only whoever holds shop.order_view_price reads it.
            protected_fields=('price',),
            # Only whoever may approve writes these, and only from pending.
            status_actions={
                'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
            },
        )

    def __str__(self):
        return f'{self.item} ({self.branch})'


# --8<-- [end:order]
