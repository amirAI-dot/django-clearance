"""
What every test may ask for: people and bundles holding exactly what it names.

A permission is named ``app_label.codename``, alone or with the scope it is
given in: ``'lending.loan_view'`` or ``('lending.loan_view', 'own')``.
"""

from collections.abc import Callable, Mapping

import pytest
from django.contrib.auth.models import AnonymousUser, Group, Permission

from clearance.models import ScopeGrant
from tests.project.accounts.models import Person

Given = str | tuple[str, str]
MakeUser = Callable[..., Person]
MakeBundle = Callable[..., Group]


def permission(name: str) -> Permission:
    app_label, codename = name.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def split(given: Given) -> tuple[str, str | None]:
    return (given, None) if isinstance(given, str) else given


@pytest.fixture
def make_user(db: None) -> MakeUser:
    """
    A person holding the permissions named, directly, and the bundles given.

    The person is read back from the database, so nothing about them - Django's
    permission cache or the library's grants - is kept from before.
    """
    count = 0

    def make(
        *permissions: Given,
        bundles: tuple[Group, ...] = (),
        superuser: bool = False,
        active: bool = True,
    ) -> Person:
        nonlocal count
        count += 1
        person = Person.objects.create_user(
            username=f'person{count}', is_superuser=superuser, is_active=active
        )

        for given in permissions:
            name, scope = split(given)
            person.user_permissions.add(permission(name))

            if scope is not None:
                ScopeGrant.objects.create(user=person, permission=permission(name), scope=scope)

        person.groups.add(*bundles)
        return Person.objects.get(pk=person.pk)

    return make


@pytest.fixture
def make_bundle(db: None) -> MakeBundle:
    """A bundle holding ``grants`` - ``{permission: scope or None}`` - made directly."""
    count = 0

    def make(grants: Mapping[str, str | None], name: str = '') -> Group:
        nonlocal count
        count += 1
        bundle = Group.objects.create(name=name or f'bundle{count}')

        for name_, scope in grants.items():
            bundle.permissions.add(permission(name_))

            if scope is not None:
                ScopeGrant.objects.create(group=bundle, permission=permission(name_), scope=scope)

        return bundle

    return make


@pytest.fixture
def anonymous() -> AnonymousUser:
    return AnonymousUser()
