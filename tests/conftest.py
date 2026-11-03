"""
What every test may ask for: people with exactly the permissions it names.
"""

from collections.abc import Callable

import pytest
from django.contrib.auth.models import AnonymousUser, Permission, User

MakeUser = Callable[..., User]


@pytest.fixture
def make_user(db: None) -> MakeUser:
    """
    A person holding the permissions named, as ``app_label.codename``.

    The person is read back from the database, so Django's permission cache
    starts empty and reflects what was granted.
    """
    count = 0

    def make(*permissions: str, superuser: bool = False, active: bool = True) -> User:
        nonlocal count
        count += 1
        person = User.objects.create_user(
            username=f'person{count}', is_superuser=superuser, is_active=active
        )

        for name in permissions:
            app_label, codename = name.split('.')
            person.user_permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )

        return User.objects.get(pk=person.pk)

    return make


@pytest.fixture
def anonymous() -> AnonymousUser:
    return AnonymousUser()
