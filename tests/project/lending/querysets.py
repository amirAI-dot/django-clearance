"""Which loans, and which payments, a grant can reach."""

from collections.abc import Mapping
from typing import ClassVar

from django.db.models import Q
from django.utils.functional import Promise

from clearance.protocols import User
from clearance.querysets import OwnedQuerySet, ScopedQuerySet


class LoanQuerySet(ScopedQuerySet):  # type: ignore[type-arg]
    scopes: ClassVar[Mapping[str, str | Promise]] = {
        'own': 'Their own loans',
        'reviewing': 'The loans they review',
    }

    def scope_own(self, user: User) -> Q:
        return Q(applicant=user)

    def scope_reviewing(self, user: User) -> Q:
        return Q(officer=user)


class PaymentQuerySet(OwnedQuerySet):  # type: ignore[type-arg]
    owner_path = 'loan__applicant'
    default_scope = 'own'
