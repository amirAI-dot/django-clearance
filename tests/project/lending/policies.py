"""Who may do what with a loan. A payment has no policy: its model's is asked."""

from collections.abc import Mapping
from typing import ClassVar

from clearance.policies import BasePolicy
from clearance.protocols import User
from clearance.registry import registry
from tests.project.lending.models import Loan


class LoanPolicy(BasePolicy):
    model = Loan
    codename = 'loan'
    custom_actions: ClassVar[Mapping[str, str]] = {'approve': 'can_approve'}

    def can_approve(self, user: User, obj: object | None = None) -> bool:
        """Approving needs the permission, the loan within its scope - and not one's own."""
        if not self.has_within_scope(user, 'approve', obj):
            return False
        return obj is None or getattr(obj, 'applicant_id', None) != getattr(user, 'pk', None)


loan_access = registry.register(LoanPolicy)
