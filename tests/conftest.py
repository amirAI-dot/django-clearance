"""
What every test may ask for: people with exactly the permissions and roles it
names.
"""

from collections.abc import Callable, Iterable

import pytest
from django.contrib.auth.models import AnonymousUser, Permission

from tests.project.accounts.models import Person

MakeUser = Callable[..., Person]


@pytest.fixture
def make_user(db: None) -> MakeUser:
    """
    A person holding the permissions named, as ``app_label.codename``.

    ``role`` is their one role; ``extra_roles`` gives them more, read when a
    test points ``ROLE_ATTRIBUTE`` at ``roles``. The person is read back from
    the database, so nothing about them - permissions or roles - is cached.
    """
    count = 0

    def make(
        *permissions: str,
        role: str = '',
        extra_roles: Iterable[str] = (),
        superuser: bool = False,
        active: bool = True,
    ) -> Person:
        nonlocal count
        count += 1
        person = Person.objects.create_user(
            username=f'person{count}',
            role=role,
            extra_roles=list(extra_roles),
            is_superuser=superuser,
            is_active=active,
        )

        for name in permissions:
            app_label, codename = name.split('.')
            person.user_permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )

        return Person.objects.get(pk=person.pk)

    return make


@pytest.fixture
def anonymous() -> AnonymousUser:
    return AnonymousUser()
