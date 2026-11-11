"""
The safety rules: whoever manages access cannot give themselves everything.

The admin site manages access, so a person given ``permission_edit`` to look
after bundles must not be able to make a bundle of every permission and give
it to themselves - or to a colleague who gives it back. Four rules, each
closing a way round the others:

* **Never your own.** Nobody changes their own access, or a bundle they hold.
* **Never what you do not hold.** Putting a permission in a bundle, giving a
  bundle holding it, or granting it is handing it on, and somebody without
  it has nothing to hand on.
* **Never a wider scope than yours.** Handing on ``order_edit`` in ``all``
  while holding it only in ``branch`` would widen it - unless you hold it in
  ``all`` yourself.
* **Never nobody left to manage.** A change after which no working account
  but the superuser holds ``permission_edit`` is refused.

The superuser, and the system acting with no person behind it, are bound by
the last rule only.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db.models import Q, QuerySet

from clearance.backends import groups_lookup
from clearance.grants import Scope, grants_of
from clearance.limits import limits
from clearance.models import PermissionRevocation
from clearance.protocols import User
from clearance.querysets import EVERY_ROW

#: The permissions to manage access, by what they let a person do.
MANAGE: Mapping[str, str] = {
    'view': 'clearance.permission_view',
    'create': 'clearance.permission_create',
    'edit': 'clearance.permission_edit',
    'delete': 'clearance.permission_delete',
    'ceiling': 'clearance.role_ceiling_edit',
}


#: What each permission to manage access lets a person do, in words.
_CHANGES: Mapping[str, str] = {
    'view': 'view access',
    'create': 'create access',
    'edit': 'edit access',
    'delete': 'delete access',
    'ceiling': "change a role's ceiling",
}


class AccessRefused(PermissionDenied):
    """A change to access the safety rules refuse, saying which rule."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule


class SafetyRules:
    """The rules, for one actor. ``None`` is the system, acting with no person."""

    def __init__(self, actor: User | None) -> None:
        self.actor = actor

    @property
    def unbound(self) -> bool:
        """The superuser and the system answer only to the last rule."""
        return self.actor is None or bool(getattr(self.actor, 'is_superuser', False))

    def require_may(self, change: str) -> None:
        """The actor holds the permission to ``view``, ``create``, ``edit`` or ``delete`` access."""
        if self.unbound:
            return

        actor = self.actor
        assert actor is not None

        if not (actor.is_authenticated and actor.is_active and actor.has_perm(MANAGE[change])):
            raise AccessRefused('may_not_manage', f'You may not {_CHANGES[change]}.')

    def require_not_own(self, person: object) -> None:
        if self.unbound:
            return

        if getattr(person, 'pk', None) == getattr(self.actor, 'pk', None):
            raise AccessRefused('own_access', 'Nobody changes their own access.')

    def require_not_held(self, bundle: Group) -> None:
        if self.unbound:
            return

        holders: Any = bundle.user_set

        if holders.filter(pk=getattr(self.actor, 'pk', None)).exists():
            raise AccessRefused('own_bundle', 'Nobody changes a bundle they hold themselves.')

    def require_holds(self, grants: Mapping[str, Scope]) -> None:
        """The actor holds every permission in ``grants``, each with that scope or ``all``."""
        if self.unbound:
            return

        assert self.actor is not None
        held = grants_of(self.actor)
        missing, wider = [], []

        for permission, scope in sorted(grants.items()):
            scopes = held.scopes(permission)

            if scopes is None:
                missing.append(permission)
            elif EVERY_ROW not in scopes and scope not in scopes:
                wider.append(f'{permission} ({scope or "no scope"})')

        if missing:
            raise AccessRefused(
                'not_held', f'You cannot give a permission you do not hold: {", ".join(missing)}.'
            )

        if wider:
            raise AccessRefused(
                'scope_not_held',
                f'You cannot give a permission with a scope you do not hold it with: '
                f'{", ".join(wider)}.',
            )

    @contextmanager
    def keeping_somebody_managing(self) -> Iterator[None]:
        """Refuses the change, inside its transaction, if it leaves nobody to manage access."""
        somebody_could = somebody_holds(MANAGE['edit'])

        yield

        if somebody_could and not somebody_holds(MANAGE['edit']):
            raise AccessRefused(
                'nobody_left',
                'After this nobody but the superuser could manage access. '
                'Give somebody else permission_edit first.',
            )


def somebody_holds(permission: str) -> bool:
    """
    Whether any working account but the superuser holds ``permission`` -
    each one found asked as the backend would, so a ceiling counts.
    """
    return any(person.has_perm(permission) for person in holders_of(permission).iterator())


def holders_of(permission: str) -> 'QuerySet[Any]':
    """
    The working accounts given ``permission`` - directly, or through a bundle
    they were given or start with, and not taken away. The superuser is left
    out: they hold everything by the flag. A ceiling is the backend's to
    apply: ``somebody_holds`` asks it.
    """
    app_label, codename = permission.split('.', 1)
    row = Permission.objects.filter(content_type__app_label=app_label, codename=codename)
    groups = Group.objects.filter(permissions__in=row)
    revoked = PermissionRevocation.objects.filter(permission__in=row).values('user')
    people = get_user_model().objects.filter(is_active=True, is_superuser=False)
    group_field = groups_lookup().removeprefix('group__')

    starting = limits().people_starting_with(groups).values('pk')
    through_bundles = Q(pk__in=groups.values(group_field)) | Q(pk__in=starting)

    return people.filter(
        Q(user_permissions__in=row) | (through_bundles & ~Q(pk__in=revoked))
    ).distinct()
