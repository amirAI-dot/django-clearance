"""
Roles' starting bundles and ceilings, as conditions inside the queries the
backend and the grants already make - installed when the app starts.

A person's ceiling is the union of their roles' ceilings. A person with no
role, or with any role that is not limited, has none: roles limit, they do
not stand in for bundles.
"""

from typing import Any

from django.contrib.auth.models import Group
from django.db.models import Exists, OuterRef, Q, QuerySet

from clearance.limits import Limits
from clearance.protocols import User
from clearance.roles.models import Role, RoleCeiling
from clearance.roles.resolvers import resolver


class RoleLimits(Limits):
    def starting_bundles(self, user: User) -> 'QuerySet[Group]':
        return Group.objects.filter(role_bundles__role__in=resolver().roles(user))

    def allowed(self, user: User, permission: str) -> Q:
        roles = resolver().roles(user)
        in_a_ceiling = RoleCeiling.objects.filter(
            role__in=roles, permission_id=OuterRef(permission)
        )
        return ~Q(Exists(roles)) | Q(Exists(roles.filter(limited=False))) | Q(Exists(in_a_ceiling))

    def people_starting_with(self, bundles: 'QuerySet[Group]') -> 'QuerySet[Any]':
        return resolver().holders(Role.objects.filter(bundles__group__in=bundles))

    def describe(self, user: User) -> list[str]:
        return [str(role) for role in resolver().roles(user)]
