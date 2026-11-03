"""
The library installs into a Django project and the project still starts.

If any of these fails, nothing else in the suite means anything: the package
was not installed, the app did not load, or the suite is not running against
the database it claims to.
"""

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


# Django's own model checks may ask the database what it supports - on SQLite,
# whether JSONField works - so the check needs the database.
@pytest.mark.django_db
def test_a_project_with_the_library_passes_djangos_checks() -> None:
    call_command('check', fail_level='WARNING')


@pytest.mark.django_db
def test_the_suite_runs_on_the_database_it_was_asked_for() -> None:
    expected = {'sqlite': 'sqlite', 'postgres': 'postgresql'}[settings.TEST_DATABASE]

    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')

    assert connection.vendor == expected
