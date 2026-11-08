"""
The roles pages of the admin site: every role, and each one's name, ceiling,
starting bundles and people.

Looking needs ``clearance.permission_view``; every change goes through
``RoleService``, so a ceiling changes only for whoever holds
``role_ceiling_edit``, and the rest of the safety rules hold as in code.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import URLPattern, path
from django.utils.translation import gettext as _

from clearance.admin.standing import name_of
from clearance.admin.views import PageSet
from clearance.models import Declared
from clearance.protocols import user_of
from clearance.roles.models import Role
from clearance.roles.resolvers import resolver
from clearance.roles.services import RoleService
from clearance.safety import AccessRefused


class RolePages(PageSet):
    """Mounted under ``access/roles/`` by ``clearance.roles.admin``."""

    template_dir = 'clearance/roles'

    def get_urls(self) -> list[URLPattern]:
        wrap = self.site.admin_view
        return [
            path('roles/', wrap(self.roles), name='clearance_roles'),
            path('roles/add/', wrap(self.add_role), name='clearance_role_add'),
            path('roles/<int:pk>/', wrap(self.role), name='clearance_role'),
            path('roles/<int:pk>/delete/', wrap(self.delete_role), name='clearance_role_delete'),
        ]

    def menu(self, request: HttpRequest) -> list[dict[str, Any]]:
        return [
            {
                'name': _('Roles'),
                'object_name': 'Role',
                'admin_url': self.url('clearance_roles'),
                'add_url': self.url('clearance_role_add') if self.may(request, 'create') else None,
                'view_only': not self.may(request, 'edit'),
            }
        ]

    # ------------------------------------------------------------------ pages

    def roles(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        roles = Role.objects.annotate(
            permitted=Count('ceiling', distinct=True),
            starting=Count('bundles', distinct=True),
            people=Count('assignments', distinct=True),
        )
        return self.render(
            request,
            'roles',
            _('Roles'),
            roles=roles,
            assigns=resolver().assigns,
            declared=Declared.keys('role'),
        )

    def add_role(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        errors: list[str] = []
        code, name = request.POST.get('code', '').strip(), request.POST.get('name', '').strip()

        if request.method == 'POST':
            try:
                role = RoleService(actor=user_of(request)).create_role(code, name or code)
            except (AccessRefused, ValidationError) as error:
                errors = _messages_of(error)
            else:
                messages.success(request, _('The role %(name)s was made.') % {'name': role.name})
                return self.redirect('clearance_role', role.pk)

        return self.render(
            request, 'role_add', _('Add a role'), code=code, name=name, errors=errors
        )

    def role(self, request: HttpRequest, pk: int) -> HttpResponse:
        self.require(request, 'view')
        role = get_object_or_404(Role, pk=pk)

        if request.method == 'POST':
            self._change(request, role)
            return self.redirect('clearance_role', pk)

        service = RoleService(actor=user_of(request))
        ceiling = service.ceiling_of(role)
        declared = Declared.holds('role', role.code)
        starting = list(Group.objects.filter(role_bundles__role=role).order_by('name'))
        return self.render(
            request,
            'role',
            role.name,
            role=role,
            ceiling=ceiling,
            rows=_ceiling_rows(ceiling or frozenset()),
            starting=starting,
            other_bundles=Group.objects.exclude(pk__in=[b.pk for b in starting]).order_by('name'),
            people=resolver().holders(Role.objects.filter(pk=role.pk)).order_by('pk'),
            assigns=resolver().assigns,
            may_ceiling=self.may(request, 'ceiling') and not declared,
            declared=declared,
        )

    def delete_role(self, request: HttpRequest, pk: int) -> HttpResponse:
        self.require(request, 'view')
        role = get_object_or_404(Role, pk=pk)

        if request.method == 'POST':
            try:
                RoleService(actor=user_of(request)).delete_role(role)
            except AccessRefused as error:
                messages.error(request, str(error))
                return self.redirect('clearance_role', pk)

            messages.success(request, _('The role %(name)s was deleted.') % {'name': role.name})
            return self.redirect('clearance_roles')

        return self.render(
            request, 'role_delete', _('Delete %(name)s') % {'name': role.name}, role=role
        )

    # ------------------------------------------------------------------ helpers

    def _change(self, request: HttpRequest, role: Role) -> None:
        """One change to a role, from its page; the service decides."""
        service, data, done = RoleService(actor=user_of(request)), request.POST, ''

        try:
            match data.get('do'):
                case 'rename':
                    service.rename_role(role, data.get('name', '').strip() or role.name)
                    done = _('The role was renamed.')
                case 'ceiling':
                    limited = data.get('limited') == 'on'
                    service.set_ceiling(role, data.getlist('permit') if limited else None)
                    done = _('The ceiling was changed.')
                case 'give':
                    service.give_bundle(role, get_object_or_404(Group, pk=data.get('bundle')))
                    done = _('Everybody with the role now starts with the bundle.')
                case 'take':
                    service.take_bundle(role, get_object_or_404(Group, pk=data.get('bundle')))
                    done = _('Nobody with the role starts with the bundle any more.')
                case 'assign':
                    service.assign(_person(data.get('person', '')), role)
                    done = _('The role was given.')
                case 'unassign':
                    service.unassign(_person(data.get('person', '')), role)
                    done = _('The role was taken away.')
                case _:
                    messages.error(request, _('Nothing was asked for.'))
                    return
        except (AccessRefused, ValidationError) as error:
            for message in _messages_of(error):
                messages.error(request, message)
            return

        messages.success(request, done)


def _ceiling_rows(ceiling: frozenset[str]) -> list[tuple[str, list[tuple[str, str, bool]]]]:
    """Every permission, by model: ``(model, [(name, label, permitted)])`` - one query."""
    rows: dict[str, list[tuple[str, str, bool]]] = {}

    for permission in Permission.objects.select_related('content_type').order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    ):
        model = permission.content_type.model_class()

        if model is not None:
            label = f'{model._meta.app_config.verbose_name}: {model._meta.verbose_name_plural}'
            name = name_of(permission)
            rows.setdefault(label, []).append((name, str(permission.name), name in ceiling))

    return list(rows.items())


def _person(found: str) -> Any:
    """The person a page names, by their username or their id."""
    people = get_user_model().objects
    field = get_user_model().USERNAME_FIELD
    person = people.filter(**{field: found}).first()

    if person is None and found.isdigit():
        person = people.filter(pk=found).first()

    if person is None:
        raise ValidationError(_('There is nobody called %(name)s.') % {'name': found})

    return person


def _messages_of(error: AccessRefused | ValidationError) -> list[str]:
    return list(error.messages) if isinstance(error, ValidationError) else [str(error)]
