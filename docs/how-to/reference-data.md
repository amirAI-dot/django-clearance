# Reference data everybody reads

A list of branches, the kinds of loan: everybody signed in reads them, to
choose one, and few change them. Gating the reads protects nothing and makes
every form refuse a choice.

## The rows

```python
from clearance.querysets import SignedInReadQuerySet


class Branch(models.Model):
    name = models.CharField(max_length=80)

    objects = SignedInReadQuerySet.as_manager()
```

Every row, for anybody signed in, whatever they hold - so a serializer's or
a form's field choosing a branch offers every branch. Somebody signed out, or
switched off, reaches none.

## The writes

Who may change a branch is still a permission: `change_branch`, given like
any other. For an API that lists branches to anybody signed in, give the
model a policy that reads the same way:

```python
from clearance.policies import SignedInReadPolicy
from clearance.registry import registry


class BranchPolicy(SignedInReadPolicy):
    model = Branch


registry.register(BranchPolicy)
```

Reading is open to anybody signed in; creating, editing and deleting ask the
permissions.
