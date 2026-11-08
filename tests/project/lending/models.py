"""
A small lending app, the resource the suite guards.

Loans are applied for by customers and approved by officers - enough to give
a policy something to decide about, with an action beyond the standard four.
A loan declares its own permissions (``loan_view``); a payment keeps
Django's (``view_payment``), so the suite holds both styles.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from clearance.permissions import DEFAULT_ACTIONS, build_permissions
from tests.project.lending.querysets import LoanQuerySet, PaymentQuerySet


class Loan(models.Model):
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loans'
    )
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loans_to_review',
    )
    amount = models.PositiveIntegerField()
    approved = models.BooleanField(default=False)
    region = models.CharField(max_length=32, blank=True)
    status = models.CharField(
        max_length=16,
        choices=(('pending', 'Pending'), ('approved', 'Approved'), ('declined', 'Declined')),
        default='pending',
    )

    objects = LoanQuerySet.as_manager()

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


class Payment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.PositiveIntegerField()

    objects = PaymentQuerySet.as_manager()

    def __str__(self) -> str:
        return f'Payment {self.pk} of {self.amount}'


class Statement(models.Model):
    """Nothing about access here at all: Django's permissions, a plain manager."""

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='statements')
    region = models.CharField(max_length=32, blank=True)
    total = models.PositiveIntegerField()
    issued_on = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f'Statement {self.pk}'
