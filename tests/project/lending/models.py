"""
A small lending app, the resource the suite guards.

Loans are applied for by customers and approved by officers - enough to give
a policy something to decide about, with an action beyond the standard four.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from clearance.permissions import DEFAULT_ACTIONS, build_permissions


class Loan(models.Model):
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loans'
    )
    amount = models.PositiveIntegerField()

    class Meta:
        default_permissions = ()
        permissions = build_permissions(
            'loan',
            _('loans'),
            actions=(*DEFAULT_ACTIONS, 'approve', 'look_up'),
            labels={'approve': _('Can approve or decline %(resource)s')},
        )

    def __str__(self) -> str:
        return f'Loan {self.pk} for {self.amount}'
