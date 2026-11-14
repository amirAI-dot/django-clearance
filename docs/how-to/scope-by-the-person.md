# Scope rows by a field of the person

Each person reaches their region's rows: a loan officer in the north sees the
north's loans. The person's region is a field of the user.

## As a rule, with no code

In the admin site, *Access*, *Row scopes*, build a rule for loans:

```text
region      is          the person's region
```

Or in code, as the admin site does:

```python
from clearance.services import AccessService

AccessService(actor=request.user).create_scope_rule(
    Loan,
    'region',
    'Their region',
    [{'field': 'region', 'operator': 'is', 'value': {'person': 'region'}}],
)
```

`{'person': 'region'}` is the person's `region`; `{'person': ''}` is the
person themselves; `{'person': 'branch__city'}` reaches through a relation.

## Or in code

```python
class LoanQuerySet(ScopedQuerySet):
    scopes = {'region': _('Their region')}

    def scope_region(self, user):
        return Q(region=getattr(user, 'region', None))
```

## Nobody moves themselves

A person who could write their own `region` would reach another region's
loans - changing their own access. So nobody writes, on their own account, a
field that decides which rows they reach; somebody else who may change the
account still does.

A rule scope's fields are known to the library and locked by themselves. A
scope in code is code, so name the fields it reads:

```python
CLEARANCE = {'PERSON_FIELDS': ['region']}
```

The field is then locked on a person's own page in the admin site, in a
protected form, and refused by the API - unless it is sent back as it is.
