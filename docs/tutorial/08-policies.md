# 8. Policies

Everything so far was a permission and a scope, and needed no code to
decide. One rule of the shop is not about who is asking, but about the
order: nobody edits it once it is delivered. That is a policy:

```python
--8<-- "example/shop/policies.py"
```

* A model with no policy is asked through `ModelPolicy`: its permission,
  within its scope. A policy is written only for a rule no permission can
  say.
* A hook is `can_<action>`. `has_within_scope` is the permission and the
  scope - what the model would answer with no policy - and the hook adds
  its own rule after it.
* `obj=None` is the question asked of a list, before any row: "may they edit
  orders at all?"

Register it where it is imported at start-up - the shop imports it in its
app's `ready()`:

```python
--8<-- "example/shop/apps.py"
```

## Asking it

Every door asks the policy - the admin site, Django's views and the API -
and so can a project:

```python
from shop.policies import order_access

order_access.policy.allows(user, 'edit', order)
order_access.policy.authorize(user, 'edit', order)    # PermissionDenied if not
```

`south_manager` holds `order_edit` in their branch, and the rug is South's -
but it is delivered, so they may not edit it, in every door.
