"""
The example shop's settings - the whole of what a project adds for the
library is marked ``clearance``.

For trying it out only: the secret key is in the file and ``DEBUG`` is on.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'only-for-the-example'  # never in a real project
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

INSTALLED_APPS = [
    # clearance: the admin site with the access pages, in place of Django's.
    'clearance.admin.apps.ClearanceAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    # clearance: the core, then the two optional apps - roles, and names in every language.
    'clearance',
    'clearance.roles',
    'clearance.translations',
    'shop',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'},
}

AUTH_USER_MODEL = 'shop.Person'

# --8<-- [start:clearance]
# clearance: the backend that reads bundles, scopes and what was taken away.
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

# clearance: every API view asks the model's policy, unless it names another.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
}

# clearance: the bundles, the status action and the roles are written in
# config/access.py, and applied by every migrate.
CLEARANCE = {
    'ACCESS': 'config.access.ACCESS',
    'SYNC_ON_MIGRATE': True,
}
# --8<-- [end:clearance]

LANGUAGE_CODE = 'en'
LANGUAGES = [('en', 'English'), ('fa', 'Persian')]
USE_I18N = True
USE_TZ = True
TIME_ZONE = 'UTC'

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/admin/login/'
