"""
What a layer above bundles adds to what a person holds: bundles they start
with, and a ceiling nothing gets past.

The core knows only this shape. ``clearance.roles`` installs its own when the
app starts - roles give starting bundles and ceilings - and without it the
answers are "no bundles" and "no ceiling", so nothing changes. The core never
imports the layer above it.

Both answers are **parts of a query**, never a query of their own: the
backend and the grants put them inside the one query they already make, so a
ceiling costs nothing to ask.
"""

from typing import Any

from django.contrib.auth.models import Group
from django.db.models import Q, QuerySet

from clearance.protocols import User


class Limits:
    """No starting bundles, no ceiling: what a project without roles has."""

    def starting_bundles(self, user: User) -> 'QuerySet[Group]':
        """The bundles ``user`` is given by what they are, not by being given them."""
        return Group.objects.none()

    def allowed(self, user: User, permission: str) -> Q:
        """
        The condition that a permission is within ``user``'s ceiling -
        ``permission`` names the column holding its id in the query it joins.
        """
        return Q()

    def people_starting_with(self, bundles: 'QuerySet[Group]') -> 'QuerySet[Any]':
        """Everybody given any of ``bundles`` by what they are - for the safety rules."""
        from django.contrib.auth import get_user_model

        return get_user_model().objects.none()

    def describe(self, user: User) -> list[str]:
        """What ``user`` is, in words - shown on their page in the admin site."""
        return []


_installed: Limits = Limits()


def limits() -> Limits:
    """The limits in force."""
    return _installed


def install(installed: Limits) -> None:
    """Put ``installed`` in force - called by the layer above when its app starts."""
    global _installed
    _installed = installed


def uninstall() -> None:
    """Back to no limits."""
    install(Limits())
