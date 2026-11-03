"""
The shape of a person, as the library sees one.

Every decision here is asked about a user, and the library never needs a
particular user model to ask it - only these three things. Django's own
``User``, a project's custom user built on ``PermissionsMixin`` and
``AnonymousUser`` all have them, so a policy can be asked about anybody a
request can carry, signed in or not.
"""

from typing import Protocol, cast

from django.http import HttpRequest


class User(Protocol):
    @property
    def is_authenticated(self) -> bool: ...

    @property
    def is_active(self) -> bool: ...

    def has_perm(self, perm: str, obj: object | None = None) -> bool: ...


def user_of(request: HttpRequest) -> User:
    """
    The person a request carries, as the library sees them.

    Django types ``request.user`` as its own base classes, which promise less
    than every real user has; this is the one place that says so.
    """
    return cast(User, request.user)
