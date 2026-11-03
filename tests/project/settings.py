"""
The project the test suite runs against.

The smallest project the library can be installed in: Django's ``auth`` and
``contenttypes``, which the permission tables need, and the library itself.
Each later stage adds what it tests and nothing more.

The database is chosen by ``CLEARANCE_TEST_DATABASE`` - ``sqlite`` (the
default) or ``postgres``, configured by the standard ``PG*`` variables - so
one suite proves the same things on both.
"""

import os

from django.core.exceptions import ImproperlyConfigured

SECRET_KEY = 'only-for-the-test-suite'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'clearance',
    'tests.project.lending',
]

_DATABASES = {
    'sqlite': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
    'postgres': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('PGDATABASE', 'clearance'),
        'USER': os.environ.get('PGUSER', 'postgres'),
        'PASSWORD': os.environ.get('PGPASSWORD', 'postgres'),
        'HOST': os.environ.get('PGHOST', 'localhost'),
        'PORT': os.environ.get('PGPORT', '5432'),
    },
}

TEST_DATABASE = os.environ.get('CLEARANCE_TEST_DATABASE', 'sqlite')

if TEST_DATABASE not in _DATABASES:
    raise ImproperlyConfigured(
        f'CLEARANCE_TEST_DATABASE must be one of {sorted(_DATABASES)}, not {TEST_DATABASE!r}.'
    )

DATABASES = {'default': _DATABASES[TEST_DATABASE]}
