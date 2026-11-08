"""
The row scope pages: every scope each model offers - its code scopes and its
rule scopes - with the grants that use each, and the rule builder.

A rule is a name, *all of* or *any of*, and conditions: a field, an operator
and a value - a constant, or something of the person's. The page offers three
conditions and a script adds more; without the script the form still works,
three at a time. Saving goes through ``AccessService``, which checks every
condition and names each one that is wrong.
"""

from collections.abc import Iterator, Mapping
from typing import Any

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Count, Model
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import URLPattern, path
from django.utils.translation import gettext as _

from clearance.admin.views import PageSet
from clearance.fields import Protection, field_names
from clearance.models import ScopeGrant, ScopeRule
from clearance.protocols import user_of
from clearance.querysets import ScopedQuerySet, code_scopes
from clearance.rules import MATCHES, OPERATORS
from clearance.safety import AccessRefused
from clearance.services import AccessService

#: How many empty conditions a new rule's page offers, for a browser without the script.
BLANK_CONDITIONS = 3


class ScopePages(PageSet):
    def get_urls(self) -> list[URLPattern]:
        wrap = self.site.admin_view
        return [
            path('scopes/', wrap(self.scopes), name='clearance_scopes'),
            path('scopes/add/', wrap(self.rule), name='clearance_scope_add'),
            path('scopes/<int:pk>/', wrap(self.rule), name='clearance_scope'),
            path('scopes/<int:pk>/delete/', wrap(self.delete_rule), name='clearance_scope_delete'),
        ]

    def menu(self, request: HttpRequest) -> list[dict[str, Any]]:
        return [
            {
                'name': _('Row scopes'),
                'object_name': 'ScopeRule',
                'admin_url': self.url('clearance_scopes'),
                'add_url': None,
                'view_only': not self.may(request, 'edit'),
            }
        ]

    # ------------------------------------------------------------------ pages

    def scopes(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        return self.render(
            request, 'scopes', _('Row scopes'), rows=list(_scope_rows()), models=self.models()
        )

    def rule(self, request: HttpRequest, pk: int | None = None) -> HttpResponse:
        self.require(request, 'view')
        rule = get_object_or_404(ScopeRule, pk=pk) if pk is not None else None
        model = (
            rule.content_type.model_class()
            if rule is not None
            else self.model_named(request.GET.get('model', ''))
        )
        assert model is not None  # a rule's model is never deleted from under it
        errors: list[str] = []
        form = _form_of(rule) if rule is not None else {'code': '', 'name': '', 'match': 'all'}
        conditions = list(rule.conditions) if rule is not None else []

        if request.method == 'POST':
            form = {key: request.POST.get(key, '').strip() for key in ('code', 'name', 'match')}
            conditions = list(conditions_from(request.POST))
            access = AccessService(actor=user_of(request))

            try:
                if rule is None:
                    rule = access.create_scope_rule(
                        model, form['code'], form['name'], conditions, match=form['match']
                    )
                else:
                    access.change_scope_rule(
                        rule, name=form['name'], conditions=conditions, match=form['match']
                    )
            except (AccessRefused, ValidationError) as error:
                errors = _messages_of(error)
            else:
                messages.success(request, _('The rule scope was saved.'))
                return self.redirect('clearance_scope', rule.pk)

        rows = [*map(_row_of, conditions), *([_row_of({})] * BLANK_CONDITIONS)]
        return self.render(
            request,
            'scope',
            rule.name if rule is not None else _('Add a rule scope'),
            rule=rule,
            model_label=model._meta.label,
            model_words=model._meta.verbose_name_plural,
            form=form,
            rows=rows[: max(len(conditions) + 1, BLANK_CONDITIONS)],
            errors=errors,
            operators=list(OPERATORS),
            matches=MATCHES,
            paths=list(field_paths(model)),
            person_paths=list(field_paths(get_user_model())),
            grants=_grants_using(rule) if rule is not None else 0,
        )

    def delete_rule(self, request: HttpRequest, pk: int) -> HttpResponse:
        self.require(request, 'view')
        rule = get_object_or_404(ScopeRule, pk=pk)

        if request.method == 'POST':
            try:
                AccessService(actor=user_of(request)).delete_scope_rule(rule)
            except (AccessRefused, ValidationError) as error:
                for message in _messages_of(error):
                    messages.error(request, message)
                return self.redirect('clearance_scope', pk)

            messages.success(request, _('The rule scope was deleted.'))
            return self.redirect('clearance_scopes')

        return self.render(
            request,
            'scope_delete',
            _('Delete %(name)s') % {'name': rule.name},
            rule=rule,
            grants=_grants_using(rule),
        )


# ---------------------------------------------------------------------- reading the form


def conditions_from(data: QueryDict) -> Iterator[dict[str, Any]]:
    """The conditions a submitted rule holds - a row with no field is a row left empty."""
    rows = zip(
        data.getlist('field'),
        data.getlist('operator'),
        data.getlist('kind'),
        data.getlist('value'),
        strict=False,
    )

    for field, operator, kind, value in rows:
        if not field.strip():
            continue

        condition: dict[str, Any] = {'field': field.strip(), 'operator': operator}

        if operator == 'is_empty':
            yield condition
        elif kind == 'person':
            yield {**condition, 'value': {'person': value.strip()}}
        elif operator == 'is_one_of':
            items = [item.strip() for item in value.split(',') if item.strip()]
            yield {**condition, 'value': {'constant': items}}
        else:
            yield {**condition, 'value': {'constant': value}}


def field_paths(model: type[Model]) -> Iterator[str]:
    """The fields a condition may name: the model's own, and one relation further."""
    protection = Protection.load()

    for name in field_names(model):
        if protection.protects(model, name) or name == 'password':
            continue

        yield name
        related = model._meta.get_field(name).related_model

        if isinstance(related, type) and related is not model:
            yield from (
                f'{name}__{further}'
                for further in field_names(related)
                if further != 'password' and not protection.protects(related, further)
            )


# ---------------------------------------------------------------------- helpers


def _scope_rows() -> Iterator[dict[str, Any]]:
    """Every scope offered anywhere, with how many grants use it."""
    used = {
        (row['permission__content_type'], row['scope']): row['count']
        for row in ScopeGrant.objects.values('permission__content_type', 'scope').annotate(
            count=Count('pk')
        )
    }
    rules = ScopeRule.objects.select_related('content_type').order_by('content_type', 'code')
    protection = Protection.load()

    for model in sorted(apps.get_models(), key=lambda model: model._meta.label):
        if isinstance(model._default_manager.all(), ScopedQuerySet):
            content_type = ContentType.objects.get_for_model(model)
            for code, label in code_scopes(model).items():
                yield {
                    'model': model._meta.label,
                    'code': code,
                    'name': str(label),
                    'rule': None,
                    'grants': used.get((content_type.pk, code), 0),
                    'broken': False,
                }

    for rule in rules:
        try:
            rule.compiled(protection)
            broken = False
        except ValidationError:
            broken = True

        yield {
            'model': rule.content_type.model_class()._meta.label  # type: ignore[union-attr]
            if rule.content_type.model_class()
            else str(rule.content_type),
            'code': rule.code,
            'name': rule.name,
            'rule': rule,
            'grants': used.get((rule.content_type_id, rule.code), 0),
            'broken': broken,
        }


def _grants_using(rule: ScopeRule) -> int:
    return ScopeGrant.objects.filter(
        scope=rule.code, permission__content_type=rule.content_type
    ).count()


def _form_of(rule: ScopeRule) -> dict[str, str]:
    return {'code': rule.code, 'name': rule.name, 'match': rule.match}


def _row_of(condition: Mapping[str, Any]) -> dict[str, str]:
    """A condition as the form shows it."""
    value = condition.get('value') or {}

    if 'person' in value:
        kind, shown = 'person', str(value['person'])
    else:
        constant = value.get('constant', '')
        kind = 'constant'
        shown = ', '.join(map(str, constant)) if isinstance(constant, list) else str(constant)

    return {
        'field': str(condition.get('field', '')),
        'operator': str(condition.get('operator', 'is')),
        'kind': kind,
        'value': shown,
    }


def _messages_of(error: AccessRefused | ValidationError) -> list[str]:
    return list(error.messages) if isinstance(error, ValidationError) else [str(error)]
