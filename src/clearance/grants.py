"""
What one person holds, and with which scopes - read once per request.

Rows a person reaches depend on the scope of every grant that gives them a
permission: each bundle that holds it, and a grant to them directly. This
reads all of them in **one query** and keeps the answer on the user object,
as Django keeps a person's permissions, so a page asking about twenty lists
reads them once.

A grant with no ``ScopeGrant`` row is a scope of ``None``: the model's
``default_scope`` decides what it reaches.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import F, OuterRef, Subquery

from clearance.backends import groups_lookup
from clearance.models import PermissionRevocation, ScopeGrant
from clearance.protocols import User, UserModel

#: Where a person's grants are kept on their user object once read.
_CACHE_ATTRIBUTE = '_clearance_grants'

#: A scope a permission is given with; ``None`` is "no scope chosen".
Scope = str | None


class Grants:
    """Every permission a person holds, each with the scopes it is given with."""

    def __init__(self, scopes: Mapping[str, frozenset[Scope]]) -> None:
        self._scopes = MappingProxyType(dict(scopes))

    @classmethod
    def from_rows(cls, rows: Iterable[tuple[str, str, Scope]]) -> 'Grants':
        """From ``(app_label, codename, scope)`` - one row per grant."""
        scopes: dict[str, set[Scope]] = {}

        for app_label, codename, scope in rows:
            scopes.setdefault(f'{app_label}.{codename}', set()).add(scope)

        return cls({name: frozenset(found) for name, found in scopes.items()})

    def holds(self, permission: str) -> bool:
        return permission in self._scopes

    def scopes(self, permission: str) -> frozenset[Scope] | None:
        """The scopes ``permission`` is given with, or ``None`` when it is not held."""
        return self._scopes.get(permission)


NOTHING = Grants({})


def grants_of(user: User) -> Grants:
    """What ``user`` holds. Somebody signed out, or switched off, holds nothing."""
    if not (user.is_authenticated and user.is_active):
        return NOTHING

    cached: Grants | None = getattr(user, _CACHE_ATTRIBUTE, None)

    if cached is None:
        cached = Grants.from_rows(_rows(cast(UserModel, user)))
        setattr(user, _CACHE_ATTRIBUTE, cached)

    return cached


def forget_grants(user: object) -> None:
    """Drop what is kept on ``user``, after their access changed - Django's caches too."""
    for attribute in (_CACHE_ATTRIBUTE, '_perm_cache', '_user_perm_cache', '_group_perm_cache'):
        if hasattr(user, attribute):
            delattr(user, attribute)


def _rows(user: UserModel) -> Any:
    """Every grant reaching ``user``, as one query: their bundles', less revocations, and theirs."""
    user_field: Any = get_user_model()._meta.get_field('user_permissions')
    by_group: Any = Group.permissions.through.objects
    by_user: Any = user_field.remote_field.through.objects
    user_column = user_field.m2m_field_name()
    revoked = PermissionRevocation.objects.filter(user=user).values('permission')

    def scope_of(**holder: object) -> Subquery:
        return Subquery(
            ScopeGrant.objects.filter(permission=OuterRef('permission_id'), **holder).values(
                'scope'
            )[:1]
        )

    through_groups = (
        by_group.filter(**{groups_lookup(): user})
        .exclude(permission_id__in=revoked)
        .annotate(
            app=F('permission__content_type__app_label'),
            code=F('permission__codename'),
            given=scope_of(group=OuterRef('group_id')),
        )
        .values_list('app', 'code', 'given')
    )
    directly = (
        by_user.filter(**{user_column: user})
        .annotate(
            app=F('permission__content_type__app_label'),
            code=F('permission__codename'),
            given=scope_of(user=user),
        )
        .values_list('app', 'code', 'given')
    )
    return through_groups.union(directly, all=True)
