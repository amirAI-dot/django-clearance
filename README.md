# django-clearance

Role, policy and row-level access control for Django. Denied by default.

[فارسی](https://github.com/amirAI-dot/django-clearance/blob/main/README.fa.md)

An administrator decides, in Django's admin site and with no code, who may
do what - and to which rows, and with which fields:

* **bundles** of permissions, each given with a **scope** - "their branch's
  orders", "their own", or a rule built in the admin site;
* **protected fields**, read with one permission and written with another;
* **status actions** - only whoever may approve sets an order to *approved*;
* **roles**, optional, with a ceiling nobody with the role goes past.

Every door asks the same rules: Django's views and templates, DRF, the admin
site, and your own code. A change is refused when it would let somebody give
themselves more. The pages, messages and permissions come in English and
Persian, and read right to left in Persian.

## In a project

```bash
pip install 'django-clearance[drf]'
```

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
    'clearance',
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

```python
class OrderViewSet(ScopedModelViewSet):  # the rows, the policy, the fields - asked
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


Order.objects.visible_to(user, 'edit')  # the orders this person may edit
```

* [The guide](https://github.com/amirAI-dot/django-clearance/blob/main/docs/guide.md) - every part, how to use it.
* [The example shop](https://github.com/amirAI-dot/django-clearance/blob/main/example/README.md) - a project using all of it, to run.
* [The design](https://github.com/amirAI-dot/django-clearance/blob/main/docs/design.md) - why it is built the way it is.

Python 3.11 to 3.14; Django 5.2, 6.0 and 6.1; Django REST framework 3.16 and
later, optional; any database Django supports.

## Working on it

Every check runs through [nox](https://nox.thea.codes), the same sessions
locally and in CI. With [uv](https://docs.astral.sh/uv/) installed, a Python
that is missing is fetched for you.

```bash
uv tool install nox
```

```bash
nox -s lint
```

```bash
nox -s types
```

```bash
nox -s tests
```

`tests` runs every supported Python and Django; one combination is
`nox -s "tests(3.13-django6.1)"`, and `nox -l` lists them all. `browser`
runs the pages in a real browser, `messages` - with gettext installed -
checks that the catalogues hold every string the library marks,
`package` builds the wheel and runs the example project on it, and `docs`
builds the documentation site - `nox -s docs -- serve` shows it as it is
written. `screenshots` takes the site's pictures of the admin site again,
from the example project.

The suite uses SQLite unless told otherwise. To run it on PostgreSQL, as CI
does, set `CLEARANCE_TEST_DATABASE=postgres`; the connection is read from the
standard `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `PGDATABASE`
variables (defaults: `localhost`, `5432`, `postgres`, `postgres`,
`clearance`).

```bash
CLEARANCE_TEST_DATABASE=postgres nox -s tests
```

After marking a string, extract it with `nox -s messages`, translate what it
added in `locale/fa/LC_MESSAGES/django.po`, and compile:

```bash
cd src/clearance && django-admin compilemessages
```

## Licence

BSD 3-Clause - see [`LICENSE`](https://github.com/amirAI-dot/django-clearance/blob/main/LICENSE).
