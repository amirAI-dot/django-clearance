"""
Every change to access, in one place: the admin site, an API and the code all
change it here, under the same safety rules, announced by the same signals.

    access = AccessService(actor=request.user)

    managers = access.create_bundle(
        'Branch managers',
        grants={'shop.view_order': 'branch', 'shop.change_order': 'branch'},
    )
    access.give_bundle(person, managers)
    access.revoke(person, 'shop.change_order', reason='Under review')

A grant maps a permission, as ``app_label.codename``, to its scope - or to
``None``, for the model's ``default_scope``. A scope the permission's model
does not offer is refused, and so is a permission nobody created.

Every change is one transaction, and its signal is sent once it commits.
Asking for what is already so is not a change: nothing is written and no
signal is sent.
"""

from collections.abc import Mapping
from typing import Any

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model

from clearance import signals
from clearance.grants import Scope, forget_grants
from clearance.models import PermissionRevocation, ScopeGrant
from clearance.protocols import User, UserModel
from clearance.querysets import EVERY_ROW, ScopedQuerySet
from clearance.safety import SafetyRules

Grants = Mapping[str, Scope]


class AccessService:
    """Makes, changes and gives out access, for one actor - ``None`` for the system."""

    def __init__(self, actor: User | None) -> None:
        self.actor = actor
        self.rules = SafetyRules(actor)

    # ------------------------------------------------------------------
    # Bundles
    # ------------------------------------------------------------------

    def create_bundle(self, name: str, grants: Grants) -> Group:
        """A new bundle, holding ``grants``."""
        self.rules.require_may('create')
        found = self._resolve(grants)
        self.rules.require_holds(grants)

        with transaction.atomic():
            bundle = Group.objects.create(name=name)
            self._set_bundle_grants(bundle, found, grants)

        self._announce(signals.bundle_created, bundle=bundle, grants=dict(grants))
        return bundle

    def change_bundle(
        self, bundle: Group, *, name: str | None = None, grants: Grants | None = None
    ) -> Group:
        """
        Rename ``bundle``, or replace what it holds - for everybody holding it.

        Renaming changes nobody's access, so even somebody holding the bundle
        may do it; changing what it holds is refused to them.
        """
        self.rules.require_may('edit')
        before = self.bundle_grants(bundle)
        renamed = name is not None and name != bundle.name
        regranted = grants is not None and dict(grants) != before
        found: dict[str, Permission] = {}

        if not renamed and not regranted:
            return bundle

        if regranted:
            assert grants is not None
            self.rules.require_not_held(bundle)
            found = self._resolve(grants)
            self.rules.require_holds({p: s for p, s in grants.items() if before.get(p, ...) != s})

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            if renamed:
                bundle.name = name  # type: ignore[assignment]
                bundle.save(update_fields=['name'])
            if regranted:
                assert grants is not None
                self._set_bundle_grants(bundle, found, grants)

        self._announce(
            signals.bundle_changed,
            bundle=bundle,
            before=before,
            after=self.bundle_grants(bundle),
            name=bundle.name,
        )
        return bundle

    def delete_bundle(self, bundle: Group) -> None:
        """Delete ``bundle``. Whoever held it stops holding what it gave."""
        self.rules.require_may('delete')
        self.rules.require_not_held(bundle)
        grants, name = self.bundle_grants(bundle), bundle.name
        holders: Any = bundle.user_set
        people = list(holders.all())

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            bundle.delete()

        for person in people:
            forget_grants(person)

        self._announce(signals.bundle_deleted, name=name, grants=grants, people=people)

    def give_bundle(self, person: UserModel, bundle: Group) -> None:
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        self.rules.require_holds(self.bundle_grants(bundle))

        if person.groups.filter(pk=bundle.pk).exists():
            return

        person.groups.add(bundle)
        forget_grants(person)
        self._announce(signals.bundle_given, person=person, bundle=bundle)

    def take_bundle(self, person: UserModel, bundle: Group) -> None:
        self.rules.require_may('edit')
        self.rules.require_not_own(person)

        if not person.groups.filter(pk=bundle.pk).exists():
            return

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            person.groups.remove(bundle)

        forget_grants(person)
        self._announce(signals.bundle_taken, person=person, bundle=bundle)

    def bundle_grants(self, bundle: Group) -> dict[str, Scope]:
        """What ``bundle`` holds: ``{permission: scope}``."""
        scopes = dict(ScopeGrant.objects.filter(group=bundle).values_list('permission_id', 'scope'))
        return {
            f'{permission.content_type.app_label}.{permission.codename}': scopes.get(permission.pk)
            for permission in bundle.permissions.select_related('content_type')
        }

    # ------------------------------------------------------------------
    # One person
    # ------------------------------------------------------------------

    def grant(self, person: UserModel, permission: str, scope: Scope = None) -> None:
        """
        Give ``person`` ``permission`` directly, in ``scope``. Granting one that
        was taken away from them gives it back; granting one they hold with
        another scope changes the scope.
        """
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        (found,) = self._resolve({permission: scope}).values()
        self.rules.require_holds({permission: scope})

        with transaction.atomic():
            restored = PermissionRevocation.objects.filter(user=person, permission=found).delete()[
                0
            ]
            already = person.user_permissions.filter(pk=found.pk).exists()
            before = self._direct_scope(person, found)
            person.user_permissions.add(found)
            self._set_scope(found, scope, user=person)

        forget_grants(person)

        if restored:
            self._announce(signals.permission_restored, person=person, permission=permission)
        if not already:
            self._announce(
                signals.permission_granted, person=person, permission=permission, scope=scope
            )
        elif before != scope:
            self._announce(
                signals.scope_changed,
                person=person,
                permission=permission,
                before=before,
                after=scope,
            )

    def revoke(self, person: UserModel, permission: str, *, reason: str = '') -> None:
        """
        Take ``permission`` from ``person``, whatever gives it: a direct grant is
        removed, and what their bundles give is subtracted for them alone.
        """
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        (found,) = self._resolve({permission: None}, scopes=False).values()

        with transaction.atomic(), self.rules.keeping_somebody_managing():
            person.user_permissions.remove(found)
            ScopeGrant.objects.filter(user=person, permission=found).delete()
            PermissionRevocation.objects.get_or_create(
                user=person,
                permission=found,
                defaults={
                    'revoked_by': self.actor if isinstance(self.actor, Model) else None,
                    'reason': reason.strip(),
                },
            )

        forget_grants(person)
        self._announce(
            signals.permission_revoked, person=person, permission=permission, reason=reason
        )

    def restore(self, person: UserModel, permission: str) -> None:
        """Undo a revocation: ``person``'s bundles give ``permission`` again."""
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        (found,) = self._resolve({permission: None}, scopes=False).values()

        if PermissionRevocation.objects.filter(user=person, permission=found).delete()[0]:
            forget_grants(person)
            self._announce(signals.permission_restored, person=person, permission=permission)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve(self, grants: Grants, *, scopes: bool = True) -> dict[str, Permission]:
        """The permission rows ``grants`` name, every scope checked against its model."""
        found: dict[str, Permission] = {}
        problems: list[str] = []

        for name, scope in grants.items():
            app_label, _, codename = name.partition('.')
            row = (
                Permission.objects.filter(content_type__app_label=app_label, codename=codename)
                .select_related('content_type')
                .first()
            )

            if row is None:
                problems.append(f'{name}: no such permission')
                continue

            if scopes and scope is not None and scope not in offered_scopes(row):
                problems.append(f'{name}: its model offers no scope {scope!r}')

            found[name] = row

        if problems:
            raise ValidationError(problems)

        return found

    def _set_bundle_grants(
        self, bundle: Group, found: Mapping[str, Permission], grants: Grants
    ) -> None:
        bundle.permissions.set(found.values())
        ScopeGrant.objects.filter(group=bundle).exclude(permission__in=found.values()).delete()

        for name, permission in found.items():
            self._set_scope(permission, grants[name], group=bundle)

        holders: Any = bundle.user_set

        for person in holders.all():
            forget_grants(person)

    def _set_scope(self, permission: Permission, scope: Scope, **holder: Any) -> None:
        if scope is None:
            ScopeGrant.objects.filter(permission=permission, **holder).delete()
        else:
            ScopeGrant.objects.update_or_create(
                permission=permission, **holder, defaults={'scope': scope}
            )

    @staticmethod
    def _direct_scope(person: UserModel, permission: Permission) -> Scope:
        return (
            ScopeGrant.objects.filter(user=person, permission=permission)
            .values_list('scope', flat=True)
            .first()
        )

    def _announce(self, signal: Any, **kwargs: Any) -> None:
        """Send ``signal`` once the change commits - never for a change rolled back."""

        def send() -> None:
            signal.send(sender=AccessService, actor=self.actor, **kwargs)

        transaction.on_commit(send)


def offered_scopes(permission: Permission) -> set[str]:
    """The scopes ``permission``'s model offers; just ``all`` for a model with no scopes."""
    model = permission.content_type.model_class()
    queryset = getattr(model, '_default_manager', None)
    rows = queryset.all() if queryset is not None else None

    if isinstance(rows, ScopedQuerySet):
        return set(rows.offered_scopes())

    return {EVERY_ROW}
