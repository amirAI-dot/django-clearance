"""
Which roles a person has.

A project keeps a person's roles wherever suits it - a column on its user
model, a list, a table of assignments - and a *resolver* reads them. The
library asks ``roles_of(user)`` and never looks anywhere else, so moving the
roles is a change of ``CLEARANCE['ROLE_RESOLVER']`` and nothing more.

Three rules hold whatever the resolver:

* somebody not signed in has no roles;
* a role the project never declared in ``ROLES`` counts for nothing - it is
  left out, and logged once, rather than granting what nobody wrote a rule
  for;
* the answer is kept on the user object for the rest of the request, so a
  page asking twenty times reads the roles once.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet

from clearance.conf import clearance_settings
from clearance.protocols import User

logger = logging.getLogger('clearance')

#: Where a person's roles are kept on their user object once worked out.
_CACHE_ATTRIBUTE = '_clearance_roles'

#: Undeclared role codes already logged, so each is reported once.
_reported: set[str] = set()


class RoleResolver(ABC):
    """Says which role codes a person has. Subclass it to keep roles anywhere."""

    @abstractmethod
    def roles_of(self, user: User) -> Iterable[str]:
        """The codes of every role ``user`` has. Never called for somebody signed out."""

    def roles_subquery(self, user: User) -> 'QuerySet[Any] | None':
        """
        The same codes as a queryset of values, when they are rows.

        A backend uses it to find a person's roles inside the query it already
        makes for their permissions, instead of in a query of its own before
        it. ``None`` - the default - means the roles are not rows.
        """
        return None


class AttributeResolver(RoleResolver):
    """
    Reads the roles off the user object - ``user.role`` unless
    ``CLEARANCE['ROLE_ATTRIBUTE']`` names another attribute.

    The attribute may hold one code, a list of codes, or nothing. Costs no
    query: whatever the attribute holds was loaded with the user.
    """

    def roles_of(self, user: User) -> Iterable[str]:
        attribute = clearance_settings.role_attribute
        value = getattr(user, attribute, None)

        if value is None or value == '':
            return ()

        if isinstance(value, str):
            return (value,)

        if isinstance(value, Iterable):
            return tuple(str(code) for code in value)

        raise ImproperlyConfigured(
            f'user.{attribute} holds {type(value).__name__}, which is neither a role code '
            f'nor a list of them. Read roles from elsewhere with a RoleResolver of your own.'
        )


def roles_of(user: User) -> frozenset[str]:
    """Every declared role ``user`` has. Somebody signed out has none."""
    if not user.is_authenticated:
        return frozenset()

    cached: frozenset[str] | None = getattr(user, _CACHE_ATTRIBUTE, None)

    if cached is not None:
        return cached

    declared = set(clearance_settings.roles)
    found = set(clearance_settings.role_resolver.roles_of(user))

    for code in sorted(found - declared - _reported):
        _reported.add(code)
        logger.warning(
            'Role %r is not in CLEARANCE["ROLES"], so it counts for nothing. '
            'Declare it, or stop giving it to people.',
            code,
        )

    roles = frozenset(found & declared)
    setattr(user, _CACHE_ATTRIBUTE, roles)
    return roles


def forget_roles(user: User) -> None:
    """Drop the roles kept on ``user``, after they changed during a request."""
    if hasattr(user, _CACHE_ATTRIBUTE):
        delattr(user, _CACHE_ATTRIBUTE)


def has_role(user: User, *roles: str) -> bool:
    """Whether ``user`` has any of ``roles``. An inactive account has none."""
    return bool(user.is_active and roles_of(user) & set(roles))


def reaches_every_row(user: User) -> bool:
    """
    Whether the queryset hands ``user`` every row: the superuser, or somebody
    with a role in ``CLEARANCE['EVERY_ROW_ROLES']``.

    For a policy asking about one object whether it must be the user's own.
    It answers *which rows*, never *what may be done* with them.
    """
    if not (user.is_authenticated and user.is_active):
        return False

    if getattr(user, 'is_superuser', False):
        return True

    return bool(roles_of(user) & clearance_settings.every_row_roles)
