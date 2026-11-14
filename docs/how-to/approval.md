# An approval only some may give

Anybody who may edit a loan may correct it; only a manager approves it, only
while it is pending, and never their own.

## 1. The action

A status action - in the model:

```python
class Loan(models.Model):
    ...

    class Meta:
        default_permissions = ()
        permissions = build_permissions(
            'loan',
            _('loans'),
            actions=(*DEFAULT_ACTIONS, 'approve'),
            status_actions={
                'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
            },
        )
```

Or with no code, in the admin site, *Access*, *Actions* - see
[Actions](../admin/actions.md). Either way `loans.loan_approve` exists, held
by nobody.

## 2. Who may

Give `loan_approve` to the managers' bundle, with the scope they approve in -
their branch, their region. Whoever lacks it is offered neither *approved*
nor *rejected*, in any form, and an API refuses either value, naming the
field.

## 3. Never their own

That is about the row, not the person, so it is a policy hook:

```python
from clearance.policies import BasePolicy
from clearance.registry import registry


class LoanPolicy(BasePolicy):
    model = Loan

    def can_approve(self, user, obj=None):
        if not self.has_within_scope(user, 'approve', obj):
            return False
        return obj is None or obj.applicant_id != user.pk


loan_access = registry.register(LoanPolicy)
```

A status action is asked of the policy with the row, so the hook holds
wherever the status is written - the admin site, a form, the API.

## 4. Asking it

```python
loan_access.policy.allows(user, 'approve', loan)
writable_values(user, Loan, 'status', loan)    # the values they may set on this loan
```
