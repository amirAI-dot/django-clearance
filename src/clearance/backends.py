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

``with_perm`` - "who holds this?" - answers by the same three, so a list of
the people to tell about an approval does not name somebody it was taken from.

Each is a condition inside the query Django already makes, and Django's
caching is kept, so asking costs exactly what it did.

It replaces ``ModelBackend`` rather than sitting beside it: Django grants a
permission when *any* backend does, so ``ModelBackend`` beside it would hand
back every revoked permission (E007).

Django's ``ModelBackend`` reads the user model when it is imported, so nothing
a ``models.py`` may import - ``clearance.querysets`` and what it needs -
imports this module.
"""

from typing import Any, cast

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.db.models import Q, QuerySet

from clearance.grants import groups_lookup
from clearance.limits import Limits, limits
from clearance.models import PermissionRevocation
from clearance.safety import holders_of


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

    def with_perm(
        self,
        perm: Any,
        is_active: bool | None = True,
        include_superusers: bool = True,
        obj: Any = None,
    ) -> 'QuerySet[Any]':
        """
        Everybody holding ``perm``, as ``has_perm`` would answer for each: not
        whoever it was taken from, whoever starts with it by their role too,
        and nobody whose ceiling stops it.
        """
        asked: Any = is_active  # Django takes None too: everybody, working or not
        people = super().with_perm(perm, asked, include_superusers, obj)  # checks what is asked

        if obj is not None:
            return people.none()

        if isinstance(perm, Permission):
            perm = f'{perm.content_type.app_label}.{perm.codename}'

        app_label, _, codename = perm.partition('.')
        row = Permission.objects.filter(content_type__app_label=app_label, codename=codename)
        holders = holders_of(perm, is_active=is_active)
        given = limits()

        if type(given) is not Limits:
            # A ceiling is each person's own: asked of each of those the permission was given.
            holders = people.model._default_manager.filter(
                pk__in=[
                    person.pk
                    for person in holders.iterator()
                    if row.filter(given.allowed(person, 'pk')).exists()
                ]
            )

        found = Q(pk__in=holders.values('pk'))

        if include_superusers:
            found |= Q(is_superuser=True)

        everybody = people.model._default_manager.filter(found)
        return everybody if is_active is None else everybody.filter(is_active=is_active)
