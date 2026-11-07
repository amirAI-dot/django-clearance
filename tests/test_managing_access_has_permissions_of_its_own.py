"""
Managing access is itself guarded by permissions, held by the superuser alone at first.

If these fail, nobody can be given the right to manage bundles without being
made a superuser, or everybody can manage them from the start.
"""

import pytest
from django.contrib.auth.models import Permission

from clearance.models import Access
from tests.conftest import MakeUser

OWN = {
    'permission_view',
    'permission_create',
    'permission_edit',
    'permission_delete',
    'role_ceiling_edit',
}


@pytest.mark.django_db
def test_migrate_creates_the_librarys_own_permissions() -> None:
    stored = set(
        Permission.objects.filter(content_type__app_label='clearance').values_list(
            'codename', flat=True
        )
    )

    assert stored == OWN


def test_the_superuser_holds_them_and_nobody_else_does_until_given(make_user: MakeUser) -> None:
    root, person = make_user(superuser=True), make_user()

    assert all(root.has_perm(f'clearance.{codename}') for codename in OWN)
    assert not any(person.has_perm(f'clearance.{codename}') for codename in OWN)
    assert make_user('clearance.permission_view').has_perm('clearance.permission_view')


def test_the_access_model_has_no_table_of_its_own() -> None:
    assert Access._meta.managed is False
    assert str(Access()) == 'access'
