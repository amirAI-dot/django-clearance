"""
Where a person's permissions come from: Django's own rule, with one subtraction.

``ClearanceBackend`` is Django's ``ModelBackend`` - what was granted to the
person, and what their bundles give - except that a permission taken away
from them (``PermissionRevocation``) is left out of what their bundles give.
The subtraction is inside the query Django already makes, and Django's
caching is kept, so asking costs exactly what it did.

It replaces ``ModelBackend`` rather than sitting beside it: Django grants a
permission when *any* backend does, so ``ModelBackend`` beside it would hand
back every revoked permission (E007).
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import QuerySet

from clearance.models import PermissionRevocation


def groups_lookup() -> str:
    """The lookup from a permission to the people holding it through a group."""
    field = get_user_model()._meta.get_field('groups')
    return f'group__{field.related_query_name()}'


class ClearanceBackend(ModelBackend):
    def _get_group_permissions(self, user_obj: Any) -> 'QuerySet[Permission]':
        revoked = PermissionRevocation.objects.filter(user=user_obj).values('permission')
        return Permission.objects.filter(**{groups_lookup(): user_obj}).exclude(pk__in=revoked)
