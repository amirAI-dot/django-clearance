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
does not offer is refused, and so is a permission nobody created. A protected
field's permission takes no scope: it is the person's, not the row's.

Every change is one transaction, and its signal is sent once it commits.
Asking for what is already so is not a change: nothing is written and no
signal is sent.
"""

from collections.abc import Mapping
from typing import Any

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model, Q
from django.utils.translation import gettext

from clearance import querysets, signals
from clearance.actions import status_action_problems, transition
from clearance.discovery import action_label
from clearance.fields import Protection, field_permissions, protection_problem
from clearance.grants import Scope, forget_grants, grants_of
from clearance.limits import limits
from clearance.models import (
    PermissionRevocation,
    ProtectedField,
    ScopeGrant,
    ScopeRule,
    StatusAction,
)
from clearance.permissions import (
    declared_protected_fields,
    declared_status_actions,
    field_label,
    permission_for,
)
from clearance.protocols import User, UserModel
from clearance.querysets import EVERY_ROW, ScopedQuerySet
from clearance.safety import AccessRefused, SafetyRules

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
        _refuse(too_long(Group, name=name))
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
        self.rules.require_not_declared('bundle', bundle.name)
        before = self.bundle_grants(bundle)
        renamed = name is not None and name != bundle.name
        regranted = grants is not None and dict(grants) != before
        found: dict[str, Permission] = {}

        if not renamed and not regranted:
            return bundle

        if renamed:
            _refuse(too_long(Group, name=str(name)))

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
        self.rules.require_not_declared('bundle', bundle.name)
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
        """
        Give ``person`` ``bundle``. Refused for one's own account, and for a
        bundle holding what the actor does not hold; giving it twice is no change.
        """
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        self.rules.require_holds(self.bundle_grants(bundle))

        if person.groups.filter(pk=bundle.pk).exists():
            return

        person.groups.add(bundle)
        forget_grants(person)
        self._announce(signals.bundle_given, person=person, bundle=bundle)

    def take_bundle(self, person: UserModel, bundle: Group) -> None:
        """
        Take ``bundle`` back from ``person`` - one given to them, not one they
        start with by their role. Refused for one's own account, and when it
        would leave nobody but the superuser able to manage access.
        """
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
        """
        Undo a revocation: ``person``'s bundles give ``permission`` again. That
        is giving it, so the actor must hold it, with every scope they give it in.
        """
        self.rules.require_may('edit')
        self.rules.require_not_own(person)
        (found,) = self._resolve({permission: None}, scopes=False).values()

        if not PermissionRevocation.objects.filter(user=person, permission=found).exists():
            return

        for scope in self._scopes_bundles_give(person, found):
            self.rules.require_holds({permission: scope})

        PermissionRevocation.objects.filter(user=person, permission=found).delete()
        forget_grants(person)
        self._announce(signals.permission_restored, person=person, permission=permission)

    # ------------------------------------------------------------------
    # Rule scopes
    # ------------------------------------------------------------------

    def create_scope_rule(
        self,
        model: type[Model],
        code: str,
        name: str,
        conditions: list[dict[str, Any]],
        *,
        match: str = 'all',
    ) -> ScopeRule:
        """
        A new rule scope for ``model``, every condition checked. Nobody holds it
        yet, so making one changes nobody's access.
        """
        self.rules.require_may('create')
        content_type = ContentType.objects.get_for_model(model)
        rule = ScopeRule(content_type=content_type, code=code, name=name, match=match)
        rule.conditions = conditions
        self._check_rule(rule)
        rule.save()
        self._announce(signals.scope_rule_saved, rule=rule, created=True)
        return rule

    def change_scope_rule(
        self,
        rule: ScopeRule,
        *,
        name: str | None = None,
        conditions: list[dict[str, Any]] | None = None,
        match: str | None = None,
    ) -> ScopeRule:
        """
        Rename ``rule``, or change the rows it reaches - for everybody holding a
        grant in it. Changing the rows is refused to whoever holds one: it would
        change their own access. And it is giving every permission granted in
        it with other rows, so the actor must hold each of them on every row:
        otherwise somebody holding nothing about a model could widen "the
        north" to every row for a colleague.
        """
        self.rules.require_may('edit')
        reaching = (
            conditions is not None and ScopeRule.stored_form(conditions) != rule.conditions
        ) or (match is not None and match != rule.match)

        if reaching:
            self._require_not_holding_rule(rule)
            self.rules.require_holds(
                {
                    f'{app_label}.{codename}': EVERY_ROW
                    for app_label, codename in self._grants_in(rule)
                    .values_list('permission__content_type__app_label', 'permission__codename')
                    .distinct()
                }
            )

        rule.name = name if name is not None else rule.name
        rule.conditions = conditions if conditions is not None else rule.conditions
        rule.match = match if match is not None else rule.match
        self._check_rule(rule)
        rule.save()
        self._announce(signals.scope_rule_saved, rule=rule, created=False)
        return rule

    def delete_scope_rule(self, rule: ScopeRule) -> None:
        """Delete ``rule`` - refused while any grant is in it, which would then reach nothing."""
        self.rules.require_may('delete')
        in_use = self._grants_in(rule).count()

        if in_use:
            raise ValidationError(
                gettext(
                    '%(name)r is the scope of %(count)s grant(s). Choose another scope for '
                    'them first.'
                )
                % {'name': rule.name, 'count': in_use}
            )

        model, code, name = rule.content_type.model_class(), rule.code, rule.name
        rule.delete()
        self._announce(signals.scope_rule_deleted, model=model, code=code, name=name)

    def _check_rule(self, rule: ScopeRule) -> None:
        """The rule's conditions, and a code no other scope of its model already has."""
        model = rule.content_type.model_class()
        problems = []

        problems += too_long(ScopeRule, code=rule.code, name=rule.name)

        if not rule.code.isidentifier():
            problems.append(
                gettext('%(code)r is not a code: use letters, digits and underscores.')
                % {'code': rule.code}
            )

        rows = model._default_manager.all() if model is not None else None
        taken = {EVERY_ROW, *(rows.scopes if isinstance(rows, ScopedQuerySet) else ())}

        if rule.code in taken:
            problems.append(
                gettext('%(code)r is already a scope of this model.') % {'code': rule.code}
            )

        try:
            compiled = rule.compiled()
        except ValidationError as error:
            problems += error.messages

        if problems:
            raise ValidationError(problems)

        # A condition reaching another model reads it: its writer may view all of it.
        crossed = {model for condition in compiled.conditions for model in condition.field.crossed}
        self.rules.require_holds(
            {permission_for(model, 'view'): EVERY_ROW for model in sorted(crossed, key=str)}
        )

    def _grants_in(self, rule: ScopeRule) -> Any:
        return ScopeGrant.objects.filter(
            scope=rule.code, permission__content_type=rule.content_type
        )

    def _require_not_holding_rule(self, rule: ScopeRule) -> None:
        if self.rules.unbound:
            return

        actor_pk: Any = getattr(self.actor, 'pk', None)
        own = self._grants_in(rule).filter(
            Q(user_id=actor_pk) | Q(group__in=Group.objects.filter(user__pk=actor_pk))
        )

        if own.exists():
            raise AccessRefused(
                'own_scope',
                gettext('Nobody changes the rows of a scope their own grants are in.'),
            )

    # ------------------------------------------------------------------
    # Protected fields
    # ------------------------------------------------------------------

    def protect_field(self, model: type[Model], field: str) -> ProtectedField:
        """
        Protect ``model.field``, making its view and edit permissions.

        Nobody holds either yet, so from now on the field is left out for
        everybody but the superuser until a bundle holding them is given out.
        A field a scope rule reads is refused: the rule would tell whoever it
        reaches what the field holds.
        """
        self.rules.require_may('create')
        protection = Protection.load()
        problem = protection_problem(model, field)

        if problem is None and protection.protects(model, field):
            problem = gettext('%(field)s is already protected.') % {
                'field': f'{model.__name__}.{field}'
            }

        if problem is not None:
            raise ValidationError(problem)

        reading = self._rules_reading(model, field, protection)

        if reading:
            raise ValidationError(
                gettext('%(field)s is read by the scope rules %(rules)s. Change them first.')
                % {'field': f'{model.__name__}.{field}', 'rules': ', '.join(reading)}
            )

        content_type = ContentType.objects.get_for_model(model)
        permissions = field_permissions(model, field)
        _refuse(
            [
                problem
                for name in permissions.values()
                if (problem := permission_taken(content_type, name)) is not None
            ]
        )
        words = model._meta.get_field(field).verbose_name  # type: ignore[union-attr]

        with transaction.atomic():
            marked = ProtectedField.objects.create(content_type=content_type, field=field)

            for action, name in permissions.items():
                Permission.objects.get_or_create(
                    content_type=content_type,
                    codename=name.partition('.')[2],
                    defaults={
                        'name': field_label(action, words, str(model._meta.verbose_name_plural))
                    },
                )

        self._forget_own()
        self._announce(signals.field_protected, model=model, field=field, permissions=permissions)
        return marked

    def unprotect_field(self, model: type[Model], field: str) -> None:
        """
        Stop protecting ``model.field``: everybody who reads the row reads it
        again. Its two permissions go, and every grant of them with them.

        Only somebody holding both may do it - otherwise it would give them a
        field they were never given - and a field protected in code is
        unprotected in code.
        """
        self.rules.require_may('delete')

        if field in declared_protected_fields(model):
            raise ValidationError(
                gettext(
                    '%(field)s is protected in code, by build_permissions; it is unprotected there.'
                )
                % {'field': f'{model.__name__}.{field}'}
            )

        content_type = ContentType.objects.get_for_model(model)
        marked = ProtectedField.objects.filter(content_type=content_type, field=field).first()

        if marked is None:
            return

        permissions = field_permissions(model, field)
        self.rules.require_holds(dict.fromkeys(permissions.values()))
        codenames = [name.partition('.')[2] for name in permissions.values()]

        with transaction.atomic():
            Permission.objects.filter(content_type=content_type, codename__in=codenames).delete()
            marked.delete()

        self._forget_own()
        self._announce(signals.field_unprotected, model=model, field=field, permissions=permissions)

    @staticmethod
    def _rules_reading(model: type[Model], field: str, protection: Protection) -> list[str]:
        """The rules that work now and would not once ``model.field`` is protected."""
        after = protection.adding(model, field)
        reading = []

        for rule in (
            ScopeRule.objects.select_related('content_type').with_conditions().order_by('code')
        ):
            try:
                rule.compiled(protection)
            except ValidationError:
                continue  # already broken - not this field's doing

            try:
                rule.compiled(after)
            except ValidationError:
                reading.append(repr(rule.code))

        return reading

    # ------------------------------------------------------------------
    # Status actions
    # ------------------------------------------------------------------

    def create_status_action(
        self,
        model: type[Model],
        code: str,
        name: str,
        field: str,
        to: list[Any],
        start: list[Any] | None = None,
    ) -> StatusAction:
        """
        A new status action: from now on only whoever is allowed ``code`` writes
        the values in ``to`` - from the values in ``start``, or from any.

        Its permission is made with it and held by nobody, so the values are
        written by nobody but the superuser until it is given out.
        """
        self.rules.require_may('create')
        start = list(start or ())
        content_type = ContentType.objects.get_for_model(model)
        codename = permission_for(model, code).partition('.')[2]
        problems = status_action_problems(model, code, field, to, start)
        problems += too_long(StatusAction, code=code, name=name)
        taken = code in declared_status_actions(model) or (
            Permission.objects.filter(content_type=content_type, codename=codename).exists()
        )

        elsewhere = permission_taken(content_type, f'{model._meta.app_label}.{codename}')

        if elsewhere is not None:
            problems.append(elsewhere)

        if taken:
            problems.append(
                gettext('%(code)r is an action %(model)s has already.')
                % {'code': code, 'model': model.__name__}
            )

        if problems:
            raise ValidationError(problems)

        with transaction.atomic():
            action = StatusAction(content_type=content_type, code=code, name=name, field=field)
            action.to_values, action.from_values = to, start
            action.save()
            Permission.objects.create(
                content_type=content_type, codename=codename, name=action_label(model, code)
            )

        self._forget_own()
        self._announce(signals.status_action_saved, action=action, created=True)
        return action

    def change_status_action(
        self,
        action: StatusAction,
        *,
        name: str | None = None,
        to: list[Any] | None = None,
        start: list[Any] | None = None,
    ) -> StatusAction:
        """
        Rename ``action``, or change the values it claims and where from.

        A value no longer claimed is written by whoever may write the row, so
        only somebody allowed the action on every row may release one. A
        ``from`` that lets it write from more values gives whoever holds it
        more: it is refused to them, whose own access it would change, and to
        whoever does not hold it, who has nothing to give - so it is the
        superuser's, and the ``ACCESS`` file's.
        """
        self.rules.require_may('edit')
        self.rules.require_not_declared('status_action', status_key(action))
        model = action.content_type.model_class()
        assert model is not None, 'the model of a status action is never deleted from under it'
        permission = permission_for(model, action.code)
        new_to = list(to) if to is not None else list(action.to_values)
        new_start = list(start) if start is not None else list(action.from_values)
        problems = status_action_problems(model, action.code, action.field, new_to, new_start)
        problems += too_long(StatusAction, name=name if name is not None else action.name)

        if problems:
            raise ValidationError(problems)

        before = transition(model, action.code, action.field, action.to_values, action.from_values)
        after = transition(model, action.code, action.field, new_to, new_start)

        if before.to - after.to:
            self.rules.require_holds({permission: querysets.EVERY_ROW})

        widens = bool(before.start) and (not after.start or bool(after.start - before.start))

        if widens and self._holds(permission):
            raise AccessRefused(
                'own_action',
                gettext('Nobody lets an action they hold write from more values.'),
            )

        if widens:
            self.rules.require_holds({permission: querysets.EVERY_ROW})

        action.name = name if name is not None else action.name
        action.to_values, action.from_values = new_to, new_start
        action.save()
        self._forget_own()
        self._announce(signals.status_action_saved, action=action, created=False)
        return action

    def delete_status_action(self, action: StatusAction) -> None:
        """
        Delete ``action`` and its permission: its values are then written by
        whoever may write the row - so only somebody allowed it on every row
        may delete it.
        """
        self.rules.require_may('delete')
        self.rules.require_not_declared('status_action', status_key(action))
        model = action.content_type.model_class()
        assert model is not None, 'the model of a status action is never deleted from under it'
        permission = permission_for(model, action.code)
        self.rules.require_holds({permission: querysets.EVERY_ROW})
        code, name = action.code, action.name

        with transaction.atomic():
            Permission.objects.filter(
                content_type=action.content_type, codename=permission.partition('.')[2]
            ).delete()
            action.delete()

        self._forget_own()
        self._announce(signals.status_action_deleted, model=model, code=code, name=name)

    def _holds(self, permission: str) -> bool:
        return not self.rules.unbound and grants_of(self.actor).holds(permission)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def check_grants(self, grants: Grants) -> None:
        """A ``ValidationError`` naming each permission or scope in ``grants`` that is not there."""
        self._resolve(grants)

    def _resolve(self, grants: Grants, *, scopes: bool = True) -> dict[str, Permission]:
        """
        The permission rows ``grants`` name, every scope checked against its
        model - in three queries, however many permissions there are.
        """
        wanted = Q()

        for name in grants:
            app_label, _, codename = name.partition('.')
            wanted |= Q(content_type__app_label=app_label, codename=codename)

        rows = (
            {
                f'{row.content_type.app_label}.{row.codename}': row
                for row in Permission.objects.filter(wanted).select_related('content_type')
            }
            if grants
            else {}
        )
        found: dict[str, Permission] = {}
        problems: list[str] = []
        protection: Protection | None = None
        rules: dict[int, set[str]] | None = None

        for name, scope in grants.items():
            row = rows.get(name)

            if row is None:
                problems.append(gettext('%(name)s: no such permission') % {'name': name})
                continue

            if scopes and scope is not None:
                model = row.content_type.model_class()
                protection = protection or Protection.load()
                rules = _rule_codes() if rules is None else rules
                offered = (
                    set(querysets.code_scopes(model)) | rules.get(row.content_type_id, set())
                    if model is not None
                    else {EVERY_ROW}
                )

                if model is not None and protection.owns(model, name):
                    problems.append(
                        gettext(
                            "%(name)s: a field's permission takes no scope - it is the "
                            "person's, not the row's"
                        )
                        % {'name': name}
                    )
                elif scope not in offered:
                    problems.append(
                        gettext('%(name)s: its model offers no scope %(scope)r')
                        % {'name': name, 'scope': scope}
                    )

            found[name] = row

        if problems:
            raise ValidationError(problems)

        return found

    def _set_bundle_grants(
        self, bundle: Group, found: Mapping[str, Permission], grants: Grants
    ) -> None:
        """What ``bundle`` holds, put in place - in a fixed number of queries."""
        bundle.permissions.set(found.values())
        ScopeGrant.objects.filter(group=bundle).delete()
        ScopeGrant.objects.bulk_create(
            ScopeGrant(group=bundle, permission=found[name], scope=scope)
            for name, scope in grants.items()
            if scope is not None
        )

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
    def _scopes_bundles_give(person: UserModel, permission: Permission) -> set[Scope]:
        """The scopes ``person``'s bundles - given, and started with - give ``permission`` in."""
        bundles = Group.objects.filter(
            Q(pk__in=person.groups.values('pk'))
            | Q(pk__in=limits().starting_bundles(person).values('pk')),
            permissions=permission,
        )
        scopes = dict(
            ScopeGrant.objects.filter(group__in=bundles, permission=permission).values_list(
                'group_id', 'scope'
            )
        )
        return {scopes.get(pk) for pk in bundles.values_list('pk', flat=True)}

    @staticmethod
    def _direct_scope(person: UserModel, permission: Permission) -> Scope:
        return (
            ScopeGrant.objects.filter(user=person, permission=permission)
            .values_list('scope', flat=True)
            .first()
        )

    def _forget_own(self) -> None:
        """What is kept on the actor, after a change to what is protected - for everybody."""
        if self.actor is not None:
            forget_grants(self.actor)

    def _announce(self, signal: Any, **kwargs: Any) -> None:
        """Send ``signal`` once the change commits - never for a change rolled back."""

        def send() -> None:
            signal.send(sender=AccessService, actor=self.actor, **kwargs)

        transaction.on_commit(send)


def permission_taken(content_type: ContentType, permission: str) -> str | None:
    """
    Why ``permission`` cannot be made for the model of ``content_type`` - another
    model of its app has one of that name - or ``None`` when it can.

    Django knows a permission by its app and its codename, so two models'
    would be one: holding ``view_order_x`` of a model ``OrderX`` would read the
    field ``x`` of ``Order``.
    """
    app_label, _dot, codename = permission.partition('.')
    other = (
        Permission.objects.filter(content_type__app_label=app_label, codename=codename)
        .exclude(content_type=content_type)
        .select_related('content_type')
        .first()
    )

    if other is None:
        return None

    return gettext(
        '%(permission)s is a permission of %(model)s already: holding that one would '
        'be holding this.'
    ) % {'permission': permission, 'model': other.content_type.model}


def _refuse(problems: list[str]) -> None:
    if problems:
        raise ValidationError(problems)


def _rule_codes() -> dict[int, set[str]]:
    """The codes of every rule scope, by the content type of its model - one query."""
    codes: dict[int, set[str]] = {}

    for content_type, code in ScopeRule.objects.values_list('content_type', 'code'):
        codes.setdefault(content_type, set()).add(code)

    return codes


def too_long(model: type[Model], **values: str) -> list[str]:
    """
    What is wrong with ``values`` - by field of ``model`` - that are longer than
    their columns: SQLite keeps them whole and PostgreSQL refuses the write, so
    it is said here, the same on both.
    """
    problems = []

    for name, value in values.items():
        longest = getattr(model._meta.get_field(name), 'max_length', None)

        if longest is not None and len(value) > longest:
            problems.append(
                gettext(
                    '%(value)r... is longer than the %(longest)s characters a %(field)s may have.'
                )
                % {'value': value[:30], 'longest': longest, 'field': name}
            )

    return problems


def status_key(action: StatusAction) -> str:
    """How the ``ACCESS`` file names a status action: ``app_label.Model.code``."""
    model = action.content_type.model_class()
    label = model._meta.label if model is not None else action.content_type.model
    return f'{label}.{action.code}'
