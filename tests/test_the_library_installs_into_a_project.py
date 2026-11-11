"""
The library installs into a Django project and the project still starts.

If any of these fails, nothing else in the suite means anything: the package
was not installed, the app did not load, or the suite is not running against
the database it claims to.
"""

import os
import subprocess
import sys
from importlib.metadata import version

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection


def test_the_app_registers_under_its_own_label() -> None:
    config = apps.get_app_config('clearance')

    assert config.name == 'clearance'


def test_the_version_is_read_from_the_installed_package() -> None:
    assert version('django-clearance')


def test_a_project_with_the_library_passes_djangos_checks() -> None:
    call_command('check', fail_level='WARNING')


@pytest.mark.django_db
def test_the_suite_runs_on_the_database_it_was_asked_for() -> None:
    expected = {'sqlite': 'sqlite', 'postgres': 'postgresql'}[settings.TEST_DATABASE]

    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')

    assert connection.vendor == expected


def test_the_librarys_migrations_hold_whatever_primary_key_a_project_defaults_to() -> None:
    """
    A project left on Django's default ``AutoField`` must find nothing to
    migrate in the library's apps - or every such project would be told to
    make a migration for a library it does not own.
    """
    done = subprocess.run(
        [
            sys.executable,
            '-m',
            'django',
            'makemigrations',
            'clearance',
            'clearance_roles',
            '--check',
            '--dry-run',
            '--settings=tests.project.autofield_settings',
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, 'PYTHONPATH': '.'},
    )

    assert done.returncode == 0, done.stdout + done.stderr
