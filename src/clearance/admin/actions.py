"""
The actions pages: status actions - made here, declared in code or in the
``ACCESS`` file - the actions found in the code, and permissions nothing
checks any more.

A status action is made in two steps: its model, then its field - a field
with choices, or yes or no - so the values it may claim can be offered as
checkboxes rather than typed. Every change goes through ``AccessService``.
"""

from typing import Any

from django.contrib import messages
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import URLPattern, path
from django.utils.translation import gettext as _

from clearance.actions import StatusActions, clean_value, values_of
from clearance.admin.views import PageSet
from clearance.discovery import find_actions
from clearance.fields import field_names
from clearance.health import findings
from clearance.models import Declared, StatusAction
from clearance.permissions import declared_status_actions
from clearance.protocols import user_of
from clearance.safety import AccessRefused
from clearance.services import AccessService, status_key


class ActionPages(PageSet):
    def get_urls(self) -> list[URLPattern]:
        wrap = self.site.admin_view
        return [
            path('actions/', wrap(self.actions), name='clearance_actions'),
            path('actions/add/', wrap(self.status_action), name='clearance_action_add'),
            path('actions/<int:pk>/', wrap(self.status_action), name='clearance_action'),
            path(
                'actions/<int:pk>/delete/', wrap(self.delete_action), name='clearance_action_delete'
            ),
        ]

    def menu(self, request: HttpRequest) -> list[dict[str, Any]]:
        return [
            {
                'name': _('Actions'),
                'object_name': 'StatusAction',
                'admin_url': self.url('clearance_actions'),
                'add_url': None,
                'view_only': not self.may(request, 'edit'),
            }
        ]

    # ------------------------------------------------------------------ pages

    def actions(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        made = StatusAction.objects.select_related('content_type').order_by('content_type', 'code')
        declared = Declared.keys('status_action')
        in_code = [
            (model._meta.label, code, spec)
            for label, _words in self.models()
            for model in [self.model_named(label)]
            for code, spec in declared_status_actions(model).items()
        ]
        return self.render(
            request,
            'actions',
            _('Actions'),
            made=[(row, status_key(row) in declared) for row in made],
            in_code=in_code,
            found=sorted(find_actions(), key=lambda action: action.permission),
            gone=[f for f in findings() if f.code == 'unaccounted_permission'],
            models=self.models(),
        )

    def status_action(self, request: HttpRequest, pk: int | None = None) -> HttpResponse:
        self.require(request, 'view')
        row = get_object_or_404(StatusAction, pk=pk) if pk is not None else None
        model = (
            row.content_type.model_class()
            if row is not None
            else self.model_named(request.GET.get('model', ''))
        )
        assert model is not None  # a status action's model is never deleted from under it
        field = row.field if row is not None else request.GET.get('field', '')
        errors: list[str] = []

        if request.method == 'POST':
            try:
                row = self._save(request, model, row, field)
            except (AccessRefused, ValidationError) as error:
                errors = (
                    list(error.messages) if isinstance(error, ValidationError) else [str(error)]
                )
            else:
                messages.success(request, _('The status action was saved.'))
                return self.redirect('clearance_action', row.pk)

        values = _values(model, field)
        declared = row is not None and Declared.holds('status_action', status_key(row))
        return self.render(
            request,
            'action',
            row.name if row is not None else _('Add a status action'),
            row=row,
            model_label=model._meta.label,
            model_words=model._meta.verbose_name_plural,
            field=field,
            fields=[name for name in field_names(model) if _values(model, name)],
            values=values,
            to={*map(str, row.to_values)} if row is not None else set(),
            start={*map(str, row.from_values)} if row is not None else set(),
            errors=errors,
            declared=declared,
            claimed_elsewhere=_claimed(model, field, row),
        )

    def delete_action(self, request: HttpRequest, pk: int) -> HttpResponse:
        self.require(request, 'view')
        row = get_object_or_404(StatusAction, pk=pk)

        if request.method == 'POST':
            try:
                AccessService(actor=user_of(request)).delete_status_action(row)
            except (AccessRefused, ValidationError) as error:
                for message in (
                    error.messages if isinstance(error, ValidationError) else [str(error)]
                ):
                    messages.error(request, message)
                return self.redirect('clearance_action', pk)

            messages.success(request, _('The status action was deleted.'))
            return self.redirect('clearance_actions')

        return self.render(
            request, 'action_delete', _('Delete %(name)s') % {'name': row.name}, row=row
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _save(
        request: HttpRequest, model: Any, row: StatusAction | None, field: str
    ) -> StatusAction:
        access, data = AccessService(actor=user_of(request)), request.POST
        to = [clean_value(model, field, value) for value in data.getlist('to')]
        start = [clean_value(model, field, value) for value in data.getlist('from')]
        name = data.get('name', '').strip()

        if row is None:
            code = data.get('code', '').strip()
            return access.create_status_action(model, code, name or code, field, to, start)

        return access.change_status_action(row, name=name or row.name, to=to, start=start)


def _values(model: Any, field: str) -> list[tuple[str, str]]:
    """``(value, how it reads)`` for every value ``field`` holds - none when it has no choices."""
    try:
        found = values_of(model, field) if field else None
    except FieldDoesNotExist:
        return []

    if found is None:
        return []

    choices = dict(getattr(model._meta.get_field(field), 'flatchoices', ()) or ())
    return sorted((str(value), str(choices.get(value, value))) for value in found)


def _claimed(model: Any, field: str, row: StatusAction | None) -> list[str]:
    """The other actions on the same field, to show what each value is claimed by already."""
    if not field:
        return []

    others = StatusActions.load().on(model, field)
    own = row.code if row is not None else None
    return sorted(
        f'{found.code}: {", ".join(sorted(map(str, found.to)))}'
        for found in others
        if found.code != own
    )
