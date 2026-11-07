"""
Where a person's roles are read from - ``CLEARANCE['ROLE_RESOLVER']``.

* ``AssignmentResolver``, the default, reads the ``RoleAssignment`` rows the
  admin site and ``RoleService`` write;
* ``AttributeResolver`` reads a field of the user model holding a role's code
  - ``CLEARANCE['ROLE_ATTRIBUTE']``, ``'role'`` unless set - for a project
  that keeps roles on its users;
* a resolver of the project's own subclasses ``RoleResolver``.

A resolver answers with querysets, never lists: they go inside the one query
every permission check makes.

In a policy, ``has_role(user, 'nurse')`` answers whose job an act is - a role
is not a permission, and the superuser holds no role by being one.
"""

from abc import ABC, abstractmethod
from functools import cache
from typing import Any, ClassVar

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.utils.module_loading import import_string

from clearance.conf import clearance_settings
from clearance.grants import KEPT_PREFIX
from clearance.protocols import User
from clearance.roles.models import Role

#: Where a person's role codes are kept on their user object once read.
_CACHE_ATTRIBUTE = f'{KEPT_PREFIX}roles_of'


class RoleResolver(ABC):
    """Reads which roles people have."""

    #: Whether ``RoleService.assign`` writes what this resolver reads.
    assigns: ClassVar[bool] = False

    @abstractmethod
    def roles(self, user: User) -> 'QuerySet[Role]':
        """The roles ``user`` has."""

    @abstractmethod
    def holders(self, roles: 'QuerySet[Role]') -> 'QuerySet[Any]':
        """Everybody with any of ``roles``."""


class AssignmentResolver(RoleResolver):
    """Roles given in the admin site, or by ``RoleService.assign``."""

    assigns = True

    def roles(self, user: User) -> 'QuerySet[Role]':
        return Role.objects.filter(assignments__user_id=getattr(user, 'pk', None))

    def holders(self, roles: 'QuerySet[Role]') -> 'QuerySet[Any]':
        return get_user_model().objects.filter(role_assignments__role__in=roles)


class AttributeResolver(RoleResolver):
    """A role's code kept in a field of the user model."""

    @property
    def attribute(self) -> str:
        return str(clearance_settings.value('ROLE_ATTRIBUTE'))

    def roles(self, user: User) -> 'QuerySet[Role]':
        code = getattr(user, self.attribute, None)
        return Role.objects.filter(code=code) if code else Role.objects.none()

    def holders(self, roles: 'QuerySet[Role]') -> 'QuerySet[Any]':
        return get_user_model().objects.filter(**{f'{self.attribute}__in': roles.values('code')})


def resolver() -> RoleResolver:
    """The resolver ``CLEARANCE['ROLE_RESOLVER']`` names."""
    return _resolver(str(clearance_settings.value('ROLE_RESOLVER')))


@cache
def _resolver(path: str) -> RoleResolver:
    found = import_string(path)

    if not (isinstance(found, type) and issubclass(found, RoleResolver)):
        raise ImproperlyConfigured(f"CLEARANCE['ROLE_RESOLVER'] {path!r} is not a RoleResolver.")

    return found()


def roles_of(user: User) -> frozenset[str]:
    """The codes of ``user``'s roles - read once per request, kept on them."""
    if not (user.is_authenticated and user.is_active):
        return frozenset()

    cached: frozenset[str] | None = getattr(user, _CACHE_ATTRIBUTE, None)

    if cached is None:
        cached = frozenset(resolver().roles(user).values_list('code', flat=True))
        setattr(user, _CACHE_ATTRIBUTE, cached)

    return cached


def has_role(user: User, *codes: str) -> bool:
    """Whether ``user`` has any of ``codes`` - whose job an act is, not whether it is allowed."""
    return bool(roles_of(user) & set(codes))
