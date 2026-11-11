"""The test project, migrating a database file of its own with SYNC_ON_MIGRATE."""

import os

from tests.project.settings import *  # noqa: F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ['CLEARANCE_SYNC_DATABASE'],
    }
}

CLEARANCE = {
    'ACCESS': 'tests.test_access_written_as_code_is_applied_by_sync.FULL',
    'SYNC_ON_MIGRATE': True,
}
