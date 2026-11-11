"""
What only the database can say is wrong - for ``clearance_check`` and the
overview page.

A system check sees the code; this sees the rows. Each finding says what it
is about and why it matters:

**errors** - something that was made to give access and now gives none,
silently:

* a rule scope that no longer checks out - a field gone, or protected since;
* a status action whose field is gone, or holds those values no more;
* a grant whose scope its model offers no more - it reaches no rows.

**warnings** - something somebody may not mean:

* a grant with no scope, on a model whose default reaches no rows;
* a permission no model, field, status action or code accounts for - an
  action gone from the code, or one made by hand. It does nothing.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db.models import Model, Q

from clearance.actions import StatusActions, clean_value, values_of
from clearance.discovery import find_actions
from clearance.fields import Protection, field_permissions
from clearance.models import ScopeGrant, ScopeRule, StatusAction
from clearance.permissions import DJANGO_VERBS, permission_for
from clearance.querysets import ScopedQuerySet, code_scopes

ERROR, WARNING = 'error', 'warning'


@dataclass(frozen=True)
class Finding:
    level: str
    #: What kind of finding: ``broken_rule``, ``lost_scope``, ...
    code: str
    message: str

    def __str__(self) -> str:
        return f'{self.level}: {self.message}'


def findings() -> list[Finding]:
    """Everything the database says is wrong, errors first."""
    found = [
        *_broken_rules(),
        *_broken_status_actions(),
        *_lost_scopes(),
        *_grants_reaching_nothing(),
        *_unaccounted_permissions(),
    ]
    return sorted(found, key=lambda finding: finding.level != ERROR)


# ---------------------------------------------------------------------- errors


def _broken_rules() -> Iterator[Finding]:
    protection = Protection.load()

    for rule in ScopeRule.objects.select_related('content_type').with_conditions().order_by('code'):
        try:
            rule.compiled(protection)
        except ValidationError as error:
            yield Finding(
                ERROR,
                'broken_rule',
                f'The rule scope {rule.code!r} of {rule.content_type} reaches nothing: '
                f'{"; ".join(error.messages)}',
            )


def _broken_status_actions() -> Iterator[Finding]:
    for row in StatusAction.objects.select_related('content_type').with_values().order_by('code'):
        model = row.content_type.model_class()
        where = f'The status action {row.code!r} of {row.content_type}'

        try:
            values = values_of(model, row.field) if model is not None else None
        except FieldDoesNotExist:
            values = None

        if model is None or values is None:
            yield Finding(
                ERROR, 'broken_status_action', f'{where} writes {row.field!r}, which is gone.'
            )
            continue

        named = {
            clean_value(model, row.field, value) for value in (*row.to_values, *row.from_values)
        }
        lost = sorted(map(str, named - values))

        if lost:
            yield Finding(
                ERROR,
                'broken_status_action',
                f'{where} names values {row.field!r} holds no more: {", ".join(lost)}.',
            )


def _lost_scopes() -> Iterator[Finding]:
    rules: dict[int, set[str]] = {}

    for content_type, code in ScopeRule.objects.values_list('content_type', 'code'):
        rules.setdefault(content_type, set()).add(code)

    grants = ScopeGrant.objects.select_related('permission__content_type', 'group', 'user')

    for grant in grants:
        model = grant.permission.content_type.model_class()

        if model is None:
            continue

        offered = set(code_scopes(model)) | rules.get(grant.permission.content_type_id, set())

        if grant.scope not in offered:
            holder = f'the bundle {grant.group}' if grant.group else f'{grant.user}'
            yield Finding(
                ERROR,
                'lost_scope',
                f'{holder} holds {_name(grant.permission)} in {grant.scope!r}, which '
                f'{model._meta.label} offers no more: it reaches no rows.',
            )


# ---------------------------------------------------------------------- warnings


def _grants_reaching_nothing() -> Iterator[Finding]:
    """Grants with no scope, of the permissions of models whose default reaches no rows."""
    models = [model for model in _models() if _defaults_to_nothing(model)]
    protection = Protection.load()

    for model in models:
        content_type = ContentType.objects.get_for_model(model)
        fields = {
            name.partition('.')[2]
            for field in protection.fields(model)
            for name in field_permissions(model, field).values()
        }
        permissions = Permission.objects.filter(content_type=content_type).exclude(
            codename__in=fields
        )
        scoped = ScopeGrant.objects.filter(permission__in=permissions)
        bundles = Group.objects.filter(permissions__in=permissions).distinct()
        people = get_user_model().objects.filter(user_permissions__in=permissions).distinct()

        for bundle in bundles:
            for permission in bundle.permissions.filter(pk__in=permissions).exclude(
                pk__in=scoped.filter(group=bundle).values('permission')
            ):
                yield _reaching_nothing(f'The bundle {bundle}', permission, model)

        for person in people:
            for permission in person.user_permissions.filter(pk__in=permissions).exclude(
                pk__in=scoped.filter(user=person).values('permission')
            ):
                yield _reaching_nothing(str(person), permission, model)


def _unaccounted_permissions() -> Iterator[Finding]:
    """Permissions of a model that nothing in the code or the database checks."""
    found = {action.permission for action in find_actions()}
    status = StatusActions.load()
    protection = Protection.load()

    for model in _models():
        accounted = (
            _model_permissions(model)
            | {permission_for(model, row.code) for row in status.of(model)}
            | {
                name
                for field in protection.fields(model)
                for name in field_permissions(model, field).values()
            }
            | found
        )
        content_type = ContentType.objects.get_for_model(model)

        for permission in Permission.objects.filter(content_type=content_type).order_by('codename'):
            if _name(permission) not in accounted:
                yield Finding(
                    WARNING,
                    'unaccounted_permission',
                    f'{_name(permission)} is checked by nothing: an action gone from the '
                    f'code, or a permission made by hand.',
                )


# ---------------------------------------------------------------------- helpers


def unheld_permissions() -> int:
    """How many permissions nobody holds - not wrong, but worth a look."""
    return Permission.objects.exclude(Q(group__isnull=False) | Q(user__isnull=False)).count()


def _models() -> list[type[Model]]:
    from django.apps import apps

    return sorted(apps.get_models(), key=lambda model: model._meta.label)


def _defaults_to_nothing(model: type[Model]) -> bool:
    rows = model._default_manager.all()
    return isinstance(rows, ScopedQuerySet) and rows.default_scope is None


def _model_permissions(model: type[Model]) -> set[str]:
    """What the model itself declares: Django's verbs, and ``Meta.permissions``."""
    meta = model._meta
    standard = {
        f'{meta.app_label}.{verb}_{meta.model_name}'
        for verb in meta.default_permissions
        if verb in DJANGO_VERBS.values()
    }
    declared = {f'{meta.app_label}.{codename}' for codename, _ in meta.permissions}
    return standard | declared


def _reaching_nothing(holder: str, permission: Permission, model: type[Model]) -> Finding:
    return Finding(
        WARNING,
        'scope_needed',
        f'{holder} holds {_name(permission)} with no scope, and {model._meta.label} '
        f'reaches no rows by default: choose a scope for it.',
    )


def _name(permission: Permission) -> str:
    return f'{permission.content_type.app_label}.{permission.codename}'
