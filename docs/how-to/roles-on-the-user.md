# Keep roles on the user model

A project whose user model has a `role` column already reads roles from it,
rather than from the roles given in the admin site.

```python
class Person(AbstractUser):
    role = models.CharField(max_length=40, blank=True)
```

```python
INSTALLED_APPS = [..., 'clearance', 'clearance.roles']

CLEARANCE = {
    'ROLE_RESOLVER': 'clearance.roles.resolvers.AttributeResolver',
    'ROLE_ATTRIBUTE': 'role',
}
```

Each value of the column is a role's code: a `Role` with the code `manager`
gives everybody whose `role` is `manager` its starting bundles and its
ceiling. The roles themselves - their ceilings and starting bundles - are
still made in the admin site or the `ACCESS` file.

## Who writes the column

Writing `role` is giving a role. So in the admin site only the superuser
writes it. A project's own form or API that writes it should be as strict:
whoever writes it gives the role, round every rule about giving one.

## In a policy

```python
from clearance.roles.resolvers import has_role

has_role(user, 'manager')
```

`AttributeResolver` reads a column, never a property: it is read inside the
one query every check makes. A role kept anywhere else - a table of the
project's, an outside directory - is a resolver of the project's own,
subclassing `RoleResolver`.
