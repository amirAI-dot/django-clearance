# Installation

## 1. Install the package

```bash
pip install django-clearance            # with Django's views and admin site
pip install 'django-clearance[drf]'     # and Django REST framework
```

`[drf]` is an *extra*: the same package, with Django REST framework installed
beside it. A project with no API leaves it out.

## 2. Add it to the settings

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'clearance',
    'clearance.roles',          # optional: roles and ceilings
    'clearance.translations',   # optional: names in every language
    # ... your own apps
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']
```

Three things to know:

* **The admin app replaces Django's.** `ClearanceAdminConfig` is Django's
  admin site with the access pages added and every page asking the rules.
  Your `ModelAdmin` classes stay as they are. It is optional: without it,
  there are no access pages, and nothing else changes.
* **The backend replaces `ModelBackend`.** It reads a person's bundles, their
  own grants and what was taken away from them. Keeping `ModelBackend` beside
  it would hand back every permission taken away, so start-up refuses it.
* **The optional apps come after `'clearance'`.**

## 3. With Django REST framework

```python
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

Every API view then asks the policy of its model. A view with no model, and
no policy named, is refused at start-up - see the [tutorial](../tutorial/09-views-and-the-api.md).

## 4. Migrate

```bash
python manage.py migrate
```

## 5. Check it

```bash
python manage.py check              # what start-up can tell
python manage.py clearance_check    # what only the database can tell
```

Django's system checks refuse, at start-up, what cannot work - a backend
missing or doubled, an optional app in the wrong place, a view that cannot
ask a policy:

| check | what is wrong |
|---|---|
| `clearance.E006` | `ClearanceBackend` is not in `AUTHENTICATION_BACKENDS` |
| `clearance.E007` | `ModelBackend` is beside it |
| `clearance.E008` | an optional app is installed without `'clearance'`, or before it |
| `clearance.E009` | a view guarded by a policy cannot ask one |
| `clearance.E016` | the admin site is not the library's |

The whole list is in the [design](../design.md).

## Next

The [quickstart](quickstart.md) gives one person access to their own rows, in
a few lines.
