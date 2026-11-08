"""
Where a person's permissions come from: Django's own rule, with what the
library adds.

``ClearanceBackend`` is Django's ``ModelBackend`` - what was granted to the
person, and what their bundles give - except that:

* a permission taken away from them (``PermissionRevocation``) is left out of
  what their bundles give;
* the bundles they start with by what they are (``clearance.limits`` - their
  roles, with ``clearance.roles``) give what any bundle gives;
* nothing gets past their ceiling.

Each is a condition inside the query Django already makes, and Django's
caching is kept, so asking costs exactly what it did.

It replaces ``ModelBackend`` rather than sitting beside it: Django grants a
permission when *any* backend does, so ``ModelBackend`` beside it would hand
back every revoked permission (E007).
"""

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import Q, QuerySet

from clearance.limits import limits
from clearance.models import PermissionRevocation


def groups_lookup() -> str:
    """The lookup from a permission to the people holding it through a group."""
    field = get_user_model()._meta.get_field('groups')
    return f'group__{field.related_query_name()}'


class ClearanceBackend(ModelBackend):
    def _get_user_permissions(self, user_obj: Any) -> 'QuerySet[Permission]':
        permissions: QuerySet[Permission] = cast(Any, super())._get_user_permissions(user_obj)
        return permissions.filter(limits().allowed(user_obj, 'pk'))

    def _get_group_permissions(self, user_obj: Any) -> 'QuerySet[Permission]':
        given = limits()
        revoked = PermissionRevocation.objects.filter(user=user_obj).values('permission')
        bundles = Q(**{groups_lookup(): user_obj}) | Q(group__in=given.starting_bundles(user_obj))
        return (
            Permission.objects.filter(bundles)
            .exclude(pk__in=revoked)
            .filter(given.allowed(user_obj, 'pk'))
            .distinct()
        )
