"""
Every change to roles, in one place, under the safety rules.

    roles = RoleService(actor=request.user)
    nurse = roles.create_role('nurse', 'Nurse')
    roles.set_ceiling(nurse, ['shop.view_order'])     # needs role_ceiling_edit
    roles.give_bundle(nurse, nurses)                  # every nurse starts with it
    roles.assign(person, nurse)

The core's rules hold - managing access needs the library's permissions,
nobody changes their own access, nobody gives what they do not hold - and
two more, because a ceiling is what stops a bundle:

* **a ceiling is changed only with ``role_ceiling_edit``** - setting one,
  lifting one, and anything that lifts one from somebody: deleting a limited
  role, taking a limited role away from a person, or giving a person under
  a ceiling a second role that widens it - one that is not limited lifts it
  altogether;
* **nobody changes what their own role holds** - its ceiling, its starting
  bundles, or whether it exists.

Every change is one transaction, and its signal is sent once it commits.
Asking for what is already so changes nothing and sends nothing.
"""

from collections.abc import Iterable
from typing import Any

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model

from clearance.grants import forget_grants
from clearance.permissions import is_action_name
from clearance.protocols import User, UserModel
from clearance.roles import signals
from clearance.roles.models import Role, RoleAssignment, RoleBundle, RoleCeiling
from clearance.roles.resolvers import resolver, roles_of
from clearance.safety import AccessRefused, SafetyRules
from clearance.services import AccessService

#: A ceiling as given and as announced: permission names, or ``None`` for none at all.
Ceiling = frozenset[str] | None


class RoleService:
    """Makes, changes and gives out roles, for one actor - ``None`` for the system."""

    def __init__(self, actor: User | None) -> None:
        self.actor = actor
        self.rules = SafetyRules(actor)

    # ------------------------------------------------------------------ roles

    def create_role(
        self,
        code: str,
        name: str,
        *,
        ceiling: Iterable[str] | None = (),
        bundles: Iterable[Group] = (),
    ) -> Role:
        """
        A new role. Nobody has it yet, so making it changes nobody's access;
        but a ceiling other than "nothing" - ``None`` is none at all - is a
        ceiling set, and needs ``role_ceiling_edit``.
        """
        self.rules.require_may('create')
        wanted: Ceiling = None if ceiling is None else frozenset(ceiling)
        bundles = list(bundles)

        if wanted is None or wanted:
            self.rules.require_may('ceiling')

        self._check_code(code)
        found = self._permissions(wanted or ())

        for bundle in bundles:
            self.rules.require_holds(self._grants_of(bundle))

        with transaction.atomic():
            role = Role.objects.create(code=code, name=name, limited=wanted is not None)
            RoleCeiling.objects.bulk_create(
                RoleCeiling(role=role, permission=permission) for permission in found
            )
            RoleBundle.objects.bulk_create(
                RoleBundle(role=role, group=bundle) for bundle in bundles
            )

        self._announce(signals.role_saved, role=role, created=True)
        return role

    def rename_role(self, role: Role, name: str) -> Role:
        """Renaming changes nobody's access, so even somebody holding the role may do it."""
        self.rules.require_may('edit')
        self.rules.require_not_declared('role', role.code)

        if name != role.name:
            role.name = name
            role.save(update_fields=['name'])
            self._announce(signals.role_saved, role=role, created=False)

        return role

    def delete_role(self, role: Role) -> None:
        """
        Delete ``role``: whoever had it loses its starting bundles - and, when it
        was limited, its ceiling, which needs ``role_ceiling_edit``.
        """
        self.rules.require_may('delete')
        self.rules.require_not_declared('role', role.code)
        self._require_not_own_role(role)

        if role.limited:
            self.rules.require_may('ceiling')

        code, name = role.code, role.name

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            role.delete()

        self._forget_own()
        self._announce(signals.role_deleted, code=code, name=name)

    # ------------------------------------------------------------------ ceilings

    def ceiling_of(self, role: Role) -> Ceiling:
        """What ``role`` lets its holders have: permission names, or ``None`` for no ceiling."""
        if not role.limited:
            return None
        rows = role.ceiling.select_related('permission__content_type')
        return frozenset(
            f'{row.permission.content_type.app_label}.{row.permission.codename}' for row in rows
        )

    def set_ceiling(self, role: Role, permissions: Iterable[str] | None) -> None:
        """
        What ``role`` lets its holders have from now on - ``None`` for no
        ceiling at all. Needs ``role_ceiling_edit``, and is refused to anybody
        holding the role.
        """
        self.rules.require_may('ceiling')
        self.rules.require_not_declared('role', role.code)
        self._require_not_own_role(role)
        before = self.ceiling_of(role)
        after: Ceiling = None if permissions is None else frozenset(permissions)

        if after == before:
            return

        found = self._permissions(after or ())

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            role.limited = after is not None
            role.save(update_fields=['limited'])
            role.ceiling.all().delete()
            RoleCeiling.objects.bulk_create(
                RoleCeiling(role=role, permission=permission) for permission in found
            )

        self._forget_own()
        self._announce(signals.ceiling_changed, role=role, before=before, after=after)

    # ------------------------------------------------------------------ starting bundles

    def give_bundle(self, role: Role, bundle: Group) -> None:
        """Everybody with ``role`` starts with ``bundle`` - the actor must hold what it gives."""
        self.rules.require_may('edit')
        self.rules.require_not_declared('role', role.code)
        self._require_not_own_role(role)
        self.rules.require_holds(self._grants_of(bundle))

        _, created = RoleBundle.objects.get_or_create(role=role, group=bundle)

        if created:
            self._announce(signals.role_saved, role=role, created=False)

    def take_bundle(self, role: Role, bundle: Group) -> None:
        """Nobody with ``role`` starts with ``bundle`` any more."""
        self.rules.require_may('edit')
        self.rules.require_not_declared('role', role.code)
        self._require_not_own_role(role)

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            deleted, _ = RoleBundle.objects.filter(role=role, group=bundle).delete()

        if deleted:
            self._announce(signals.role_saved, role=role, created=False)

    # ------------------------------------------------------------------ people

    def assign(self, person: UserModel, role: Role) -> None:
        """
        Give ``person`` ``role``: its starting bundles - which the actor must
        hold - and its ceiling. When they are under a ceiling already and the
        role would widen it, or lift it, that needs ``role_ceiling_edit``.
        """
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        self._require_assigning()

        for bundle in role.bundles.select_related('group'):
            self.rules.require_holds(self._grants_of(bundle.group))

        if self._widens_ceiling(person, role):
            self.rules.require_may('ceiling')

        _, created = RoleAssignment.objects.get_or_create(
            user=person,
            role=role,
            defaults={'assigned_by': self.actor if isinstance(self.actor, Model) else None},
        )

        if created:
            forget_grants(person)
            self._announce(signals.role_assigned, person=person, role=role)

    def unassign(self, person: UserModel, role: Role) -> None:
        """
        Take ``role`` from ``person``. When it is limited, that lifts its
        ceiling from them, and needs ``role_ceiling_edit``.
        """
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        self._require_assigning()

        if role.limited:
            self.rules.require_may('ceiling')

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            deleted, _ = RoleAssignment.objects.filter(user=person, role=role).delete()

        if deleted:
            forget_grants(person)
            self._announce(signals.role_unassigned, person=person, role=role)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _widens_ceiling(person: UserModel, role: Role) -> bool:
        """
        Whether ``role`` would let ``person`` hold what their ceiling stops now.

        Somebody with no role, or with one that is not limited, has no ceiling
        to widen. Otherwise theirs is the union of their roles' - which a role
        that is not limited lifts, and one permitting anything more widens.
        """
        held = list(resolver().roles(person))

        if not held or role in held or any(not one.limited for one in held):
            return False

        if not role.limited:
            return True

        permitted = RoleCeiling.objects.filter(role__in=held).values('permission')
        return role.ceiling.exclude(permission__in=permitted).exists()

    def _require_not_own_role(self, role: Role) -> None:
        if not self.rules.unbound and role.code in roles_of(self.actor):  # type: ignore[arg-type]
            raise AccessRefused('own_role', 'Nobody changes what their own role holds.')

    @staticmethod
    def _require_assigning() -> None:
        if not resolver().assigns:
            raise ValidationError(
                f'Roles are read by {type(resolver()).__name__}, not from what is assigned '
                f'here: give them where it reads them.'
            )

    @staticmethod
    def _check_code(code: str) -> None:
        if not is_action_name(code):
            raise ValidationError(f'{code!r} is not a code: use lowercase words joined by _.')

        if Role.objects.filter(code=code).exists():
            raise ValidationError(f'There is a role {code!r} already.')

    @staticmethod
    def _permissions(names: Iterable[str]) -> list[Permission]:
        found: list[Permission] = []
        missing: list[str] = []

        for name in sorted(names):
            app_label, _, codename = name.partition('.')
            row = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()

            if row is None:
                missing.append(name)
            else:
                found.append(row)

        if missing:
            raise ValidationError([f'{name}: no such permission' for name in missing])

        return found

    def _grants_of(self, bundle: Group) -> dict[str, Any]:
        return AccessService(actor=None).bundle_grants(bundle)

    def _forget_own(self) -> None:
        if self.actor is not None:
            forget_grants(self.actor)

    def _announce(self, signal: Any, **kwargs: Any) -> None:
        """Send ``signal`` once the change commits - never for a change rolled back."""

        def send() -> None:
            signal.send(sender=RoleService, actor=self.actor, **kwargs)

        transaction.on_commit(send)
