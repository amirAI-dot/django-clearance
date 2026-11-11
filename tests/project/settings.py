"""
The project the test suite runs against.

The smallest project the library can be installed in: Django's ``auth`` and
``contenttypes``, which the permission tables need, the library and its
backend, a user model of the project's own, and a lending app with pages to
guard. Each stage adds what it tests and nothing more.

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
    'clearance.admin.apps.ClearanceAdminConfig',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'rest_framework',
    'clearance',
    'clearance.roles',
    'clearance.translations',
    'tests.project.accounts',
    'tests.project.lending',
]

AUTH_USER_MODEL = 'accounts.Person'

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

STATIC_URL = '/static/'

LANGUAGES = [('en', 'English'), ('fa', 'Persian')]

ROOT_URLCONF = 'tests.project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

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
