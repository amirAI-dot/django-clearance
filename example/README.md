# The example shop

[فارسی](README.fa.md)

Orders placed by customers at one of two branches, managed by staff - some of
whom may see the price. Every layer of the library is in it, each in the file
you would put it in:

| what | where |
|---|---|
| the backend, DRF's default permission, the `ACCESS` file | `config/settings.py` |
| bundles and roles, as code | `config/access.py` |
| permissions, a protected field (`price`), a status action (`approve`) | `shop/models.py` |
| two row scopes in code: `own` and `branch` | `shop/querysets.py` |
| a rule no permission can say: a delivered order is never edited | `shop/policies.py` |
| the API, and an action found in the code (`print_invoice`) | `shop/api.py` |
| Django's own pages, under the same rules | `shop/views.py` |
| the admin site, with nothing about access written in it | `shop/admin.py` |
| what all of it adds up to, for each person | `shop/tests.py` |

## Running it

From the repository's root, with the library installed in a fresh
environment:

```bash
python -m venv .venv && .venv/bin/pip install -e '.[drf]'
```

```bash
cd example
```

```bash
../.venv/bin/python manage.py migrate
```

`migrate` applies `config/access.py` too (`SYNC_ON_MIGRATE`). Then make the
people and orders to try it with, and a superuser for the access pages:

```bash
../.venv/bin/python manage.py example_data
```

```bash
../.venv/bin/python manage.py createsuperuser
```

```bash
../.venv/bin/python manage.py runserver
```

Each sample password is the username - never on a real database.

| sign in as | role or bundle | reaches |
|---|---|---|
| `north_manager` | the role *Branch manager* | North's orders: read, edit, approve, print - never the price |
| `south_manager` | the role *Branch manager* | South's, the same |
| `accountant` | the bundle *Accountants* | every order, with its price; nothing changed |
| `alice`, `bob` | the role *Customer* | their own orders; new ones placed, never priced or approved |

Sign in at `/admin/`, then open `/orders/` and `/api/orders/`. The superuser
sees the access pages under *Access*: the bundles as a grid, each person's
standing, the rule builder, protected fields, actions, and roles. Choose
*Persian* in your browser and they read right to left.

## Things to try

* As `north_manager`, approve the desk lamp - then try to approve it again:
  approving writes only from *pending*.
* As `south_manager`, edit the rug: it is delivered, so the policy refuses.
* As `alice`, post `{"branch": 1, "item": "Clock", "price": "1.00"}` to
  `/api/orders/`: the answer names the price as a field she may not write.
* As the superuser, build a rule scope for orders - *status* *is* *pending* -
  and give it to somebody. Try *price* instead: a rule never reads a protected
  field, because it would tell whoever holds it what the field holds. A bundle the `ACCESS` file names shows read only:
  change it in the file, and run `python manage.py clearance_sync --dry-run`.
* `python manage.py clearance_check` - what the database holds that gives no
  access, or may not be meant.

## Its tests

```bash
../.venv/bin/python manage.py test
```

The library's own suite runs these too, on every supported Python and Django.
