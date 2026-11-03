"""Which loans each role reaches."""

from django.db.models import Q

from clearance.protocols import User
from clearance.querysets import ScopedQuerySet


class LoanQuerySet(ScopedQuerySet):  # type: ignore[type-arg]
    def scope_for_customer(self, user: User) -> Q:
        return Q(applicant=user)

    def scope_for_officer(self, user: User) -> Q:
        return Q(officer=user)
