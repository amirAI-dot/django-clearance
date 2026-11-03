"""Who may do what with a loan."""

from collections.abc import Mapping
from typing import ClassVar

from clearance.policies import BasePolicy
from clearance.protocols import User
from clearance.registry import registry


class LoanPolicy(BasePolicy):
    app_label = 'lending'
    codename = 'loan'
    custom_actions: ClassVar[Mapping[str, str]] = {'approve': 'can_approve'}

    def can_approve(self, user: User, obj: object | None = None) -> bool:
        if not self.has(user, 'approve') or not self.has_role(user, 'officer'):
            return False
        return obj is None or getattr(obj, 'applicant_id', None) != getattr(user, 'pk', None)


loan_access = registry.register(LoanPolicy)
