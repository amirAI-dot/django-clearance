# The `ACCESS` file

The bundles, status actions and roles a project always has, written as code -
reviewed like code, and the same on every machine.

```python
# config/access.py - CLEARANCE = {'ACCESS': 'config.access.ACCESS'}
ACCESS = {
    'bundles': {
        'Branch managers': {'shop.order_view': 'branch', 'shop.order_approve': 'branch'},
        'Accountants': {'shop.order_view': 'all', 'shop.order_view_price': None},
    },
    'status_actions': {                  # for a model keeping Django's permissions
        'shop.Payment': {
            'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']},
        },
    },
    'roles': {                           # with clearance.roles installed
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.order_view', 'shop.order_create'],
            'bundles': ['Customers'],
        },
    },
}
```

## `bundles`

`{name: {permission: scope}}`. A permission is `app_label.codename`; a scope
is a scope's code - `all`, a code scope, a rule scope - or `None`, for the
model's default.

## `status_actions`

`{'app_label.Model': {code: spec}}`, for a model that keeps Django's
permissions. A model declaring its own with `build_permissions` declares its
status actions there.

| key | | |
|---|---|---|
| `field` | required | a field with choices, or a boolean |
| `to` | required | the values only this action writes |
| `from` | optional | the values it writes from; left out, from any |
| `name` | optional | what the admin site shows; left out, the code, readable |

## `roles`

With `clearance.roles` installed. `{code: spec}`:

| key | | |
|---|---|---|
| `name` | optional | left out, the code, readable |
| `ceiling` | optional | a list of permissions; `None` for no ceiling; left out, nothing is permitted, as for a new role |
| `bundles` | optional | the starting bundles - declared in the file, or made in the admin site |

## What the file owns

* **The file owns what it names, and nothing else.** A sync makes what the
  file adds, changes what it changes, and deletes what it once named and
  names no more. A bundle, role or status action made in the admin site is
  never touched until the file comes to name it; from then on the file owns
  it.
* **What the file owns is read only in the admin site** - to everybody, the
  superuser too - because the next sync would put it back.
* **Who is given a bundle or a role is not the file's to say.** That stays in
  the admin site, or in a project's own code.

## Applying it

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

Or on every `migrate`, with `SYNC_ON_MIGRATE`. A sync is listed whole before
anything is written, and applied in one transaction: a sync that would leave
nobody able to manage access changes nothing. Start-up refuses a file that
cannot be read or says something that cannot be (E001); whether every
permission and scope it names exists in the database is `--check`'s to say.
