# How a question is answered

Every door - a Django view, a DRF view, the admin site, a project's own code -
asks the same question, and it is answered the same way:

```python
order_access.policy.allows(user, 'edit', order)
```

## 1. Which policy

The model's policy - the one registered for it, or `ModelPolicy`, which asks
the permission and the scope and nothing more. A view finds it from its
queryset; a view of no model names it.

## 2. Which hook

`edit` is decided by `can_edit` - or by the hook `custom_actions` maps it to.
An action with no hook of its own - `approve`, `print_invoice` - is decided
by its permission within its scope, as the four standard actions are.

## 3. The permission

The hook asks for the permission `permission_for` names - `shop.order_edit`,
or `shop.change_order` for a model keeping Django's - through Django's own
`has_perm`, so the backend answers. `ClearanceBackend` answers with:

* what the person was given directly, and what their bundles give - the ones
  given them, and the ones they start with by their role;
* less what was taken away from them;
* within their role's ceiling.

Somebody signed out, or switched off, holds nothing, whatever backend is
installed.

## 4. The scope

Holding `order_edit` is not yet holding it for *this* order. The grants of
the permission that reach the person - each with its scope - are joined into
one filter: "their branch" or "their own" or a rule. The order must be among
the rows it lets through. A grant with `all` lets every row through; a grant
with no scope reaches the model's default - no rows, unless the model says
otherwise.

## 5. The policy's own rule

Last, what the hook adds: "never a delivered order", "never your own loan".
It narrows, it never widens - the hook starts from the permission and the
scope, and refuses what they would allow.

## 6. Accounts

An account is changed or deleted only by somebody holding at least what it
holds, whatever the hook says: setting somebody's password is signing in as
them.

## The same, for a list

A list asks the same once, not row by row: `visible_to(user, 'edit')` is the
filter of step 4, applied to the queryset - one query. A row the policy's own
rule refuses is refused when it is opened or written.

## And for a field, and a value

A field is read with its view permission and written with its edit
permission, asked once per request. A status value is written by whoever
holds the action that claims it - asked of the policy with the row, so step
5 holds for it too.
