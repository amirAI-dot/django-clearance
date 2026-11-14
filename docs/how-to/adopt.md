# Adopt it in an existing project

A project that already gives out Django's permissions keeps them. Django's
groups are the library's bundles, `user.has_perm()` and `{{ perms }}` keep
working, and nothing has to be moved.

## 1. Install it

```bash
pip install django-clearance
```

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
    'clearance',
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']   # instead of ModelBackend
```

```bash
python manage.py migrate
python manage.py check
```

`check` names anything that cannot work - `ModelBackend` left beside the
new backend (E007), a view that cannot say which policy to ask (E009).

## 2. What reaches what, the day after

| the model | a grant with no scope |
|---|---|
| a plain manager - `objects = models.Manager()` | every row, as Django always gave |
| a `ScopedQuerySet` with no `default_scope` | no rows, until a scope is chosen |

So a project that installs the library and changes no model sees no change:
every existing group gives what it gave. Scoping is added model by model.

## 3. Scope one model at a time

Give the model's queryset its scopes:

```python
from clearance.querysets import ScopedQuerySet


class OrderQuerySet(ScopedQuerySet):
    scopes = {'branch': _("Their branch's orders")}

    def scope_branch(self, user):
        return Q(branch=user.branch_id)


class Order(models.Model):
    ...
    objects = OrderQuerySet.as_manager()
```

From that deploy, a grant of `shop.view_order` with no scope reaches no
orders. `clearance_check` lists every such grant, so none is missed:

```bash
python manage.py clearance_check
```

```text
warning: The bundle Branch managers holds shop.view_order with no scope, and shop.Order reaches no rows by default: choose a scope for it.
```

Choose a scope for each - in the admin site, or in the `ACCESS` file. A model
whose old behaviour should stay until then names it:

```python
class OrderQuerySet(ScopedQuerySet):
    default_scope = 'all'    # a grant with no scope reaches every row, as before
```

## 4. Ask in the views

The admin site asks by itself. A Django view or a DRF view asks once it says
so - see [Views and the API](../tutorial/09-views-and-the-api.md). A view of
your own that reads rows reads them through `visible_to`:

```python
orders = Order.objects.visible_to(request.user)
```
