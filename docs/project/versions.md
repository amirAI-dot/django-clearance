# Versions and compatibility

## What it runs on

| | supported | tested in CI |
|---|---|---|
| Python | 3.11 - 3.14 | every one |
| Django | 5.2 LTS, 6.0, 6.1 | each with every Python it supports |
| Django REST framework | 3.16 and later, optional | the latest |
| Database | any Django supports | PostgreSQL and SQLite |
| Browser, for the admin site | what Django's admin supports | the latest Chromium |

## Versions

The library is young: **alpha**, `0.x`, and its API may change before `1.0`.
A release that changes what an earlier one did, in a way a project may
notice, is a new minor version - `0.1` to `0.2` - and the
[changelog](../changelog.md) marks each such change **Changed**, with what to
do.

## Upgrading

```bash
pip install --upgrade django-clearance
python manage.py migrate
python manage.py check
python manage.py clearance_check
```

`migrate` makes any permission a new release adds - held by nobody until
given. `check` and `clearance_check` say what the new release finds wrong.

## Where it is published

* the package - [PyPI](https://pypi.org/project/django-clearance/), released
  from a tag by GitHub Actions, with no token kept anywhere;
* the code - [GitHub](https://github.com/amirAI-dot/django-clearance);
* this site - built from `main` on every change.

## Licence

BSD 3-Clause.
