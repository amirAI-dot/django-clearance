"""
The shape of a person, as the library sees one.

Every decision here is asked about a user, and the library never needs a
particular user model to ask it - only these three things. Django's own
``User``, a project's custom user built on ``PermissionsMixin`` and
``AnonymousUser`` all have them, so a policy can be asked about anybody a
request can carry, signed in or not.
"""

from typing import Protocol


class User(Protocol):
    @property
    def is_authenticated(self) -> bool: ...

    @property
    def is_active(self) -> bool: ...

    def has_perm(self, perm: str, obj: object | None = None) -> bool: ...
