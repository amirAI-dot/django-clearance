"""
The access pages of the admin site: an overview, the bundles - each edited as
a grid - the people, and every permission.

Looking needs ``clearance.permission_view``; every change goes through
``AccessService``, so it needs what the service needs and obeys the same
safety rules as the code. A refusal is shown on the page, saying which rule;
nothing here decides anything the service does not.
"""

from abc import ABC, abstractmethod
from typing import Any

from django.contrib import messages
from django.contrib.admin import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.translation import gettext as _

from clearance.admin.standing import PermissionGrid, Standing, name_of
from clearance.models import Declared, PermissionRevocation
from clearance.protocols import user_of
from clearance.safety import AccessRefused, SafetyRules
from clearance.services import AccessService

#: How many people one page of the people list shows.
PEOPLE_PER_PAGE = 50


class PageSet(ABC):
    """
    A set of access pages, mounted by ``ClearanceAdminSite`` under ``access/``
    and listed on the admin index. A layer above the core - ``clearance.roles``
    - adds its own with ``ClearanceAdminSite.add_pages``.
    """

    #: Where the pages' templates are: ``<template_dir>/<page>.html``.
    template_dir = 'clearance/admin'

    def __init__(self, site: AdminSite) -> None:
        self.site = site

    @abstractmethod
    def get_urls(self) -> list[URLPattern]:
        """The pages, each named for ``reverse``."""

    def menu(self, request: HttpRequest) -> list[dict[str, Any]]:
        """The entries these pages add to the admin index, for ``request``'s person."""
        return []

    # ------------------------------------------------------------------ helpers

    def require(self, request: HttpRequest, change: str) -> None:
        """403 unless the person may ``change`` access - ``view`` to look at it."""
        try:
            SafetyRules(user_of(request)).require_may(change)
        except AccessRefused as error:
            raise PermissionDenied(str(error)) from None

    def may(self, request: HttpRequest, change: str) -> bool:
        try:
            self.require(request, change)
        except PermissionDenied:
            return False
        return True

    def render(
        self, request: HttpRequest, template: str, title: str, **context: Any
    ) -> HttpResponse:
        request.current_app = self.site.name  # as Django's own admin views say which site
        return TemplateResponse(
            request,
            f'{self.template_dir}/{template}.html',
            {
                **self.site.each_context(request),
                'title': title,
                'may_create': self.may(request, 'create'),
                'may_edit': self.may(request, 'edit'),
                'may_delete': self.may(request, 'delete'),
                **context,
            },
        )

    def redirect(self, name: str, *args: Any) -> HttpResponseRedirect:
        return HttpResponseRedirect(self.url(name, *args))

    def url(self, name: str, *args: Any) -> str:
        return reverse(f'{self.site.name}:{name}', args=args, current_app=self.site.name)


class AccessPages(PageSet):
    """The overview, the bundles, the people and the permissions."""

    def menu(self, request: HttpRequest) -> list[dict[str, Any]]:
        view_only = not self.may(request, 'edit')
        return [
            {
                'name': _('Bundles'),
                'object_name': 'Bundle',
                'admin_url': self.url('clearance_bundles'),
                'add_url': self.url('clearance_bundle_add')
                if self.may(request, 'create')
                else None,
                'view_only': view_only,
            },
            {
                'name': _('People'),
                'object_name': 'Person',
                'admin_url': self.url('clearance_people'),
                'add_url': None,
                'view_only': view_only,
            },
            {
                'name': _('Permissions'),
                'object_name': 'Permission',
                'admin_url': self.url('clearance_permissions'),
                'add_url': None,
                'view_only': True,
            },
        ]

    def get_urls(self) -> list[URLPattern]:
        wrap = self.site.admin_view
        return [
            path('', wrap(self.overview), name='clearance_overview'),
            path('bundles/', wrap(self.bundles), name='clearance_bundles'),
            path('bundles/add/', wrap(self.bundle), name='clearance_bundle_add'),
            path('bundles/<int:pk>/', wrap(self.bundle), name='clearance_bundle'),
            path(
                'bundles/<int:pk>/delete/', wrap(self.delete_bundle), name='clearance_bundle_delete'
            ),
            path('people/', wrap(self.people), name='clearance_people'),
            path('people/<int:pk>/', wrap(self.person), name='clearance_person'),
            path('permissions/', wrap(self.permissions), name='clearance_permissions'),
        ]

    # ------------------------------------------------------------------ pages

    def overview(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        people = _with_access(get_user_model().objects.all())
        held = Q(group__isnull=False) | Q(user__isnull=False)
        return self.render(
            request,
            'overview',
            _('Access'),
            bundles=Group.objects.count(),
            people=people.count(),
            permissions=Permission.objects.count(),
            unheld=Permission.objects.exclude(held).count(),
        )

    def bundles(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        bundles = Group.objects.annotate(
            people=Count('user', distinct=True), held=Count('permissions', distinct=True)
        ).order_by('name')
        return self.render(
            request, 'bundles', _('Bundles'), bundles=bundles, declared=Declared.keys('bundle')
        )

    def bundle(self, request: HttpRequest, pk: int | None = None) -> HttpResponse:
        self.require(request, 'view')
        bundle = get_object_or_404(Group, pk=pk) if pk is not None else None
        access = AccessService(actor=user_of(request))
        grants = access.bundle_grants(bundle) if bundle is not None else {}
        name, errors = (bundle.name if bundle is not None else ''), []

        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            grants = PermissionGrid.parse(
                request.POST.getlist('grant'),
                {
                    key.removeprefix('scope:'): request.POST.get(key, '')
                    for key in request.POST
                    if key.startswith('scope:')
                },
            )
            errors = self._bundle_errors(name, bundle)

            if not errors:
                try:
                    if bundle is None:
                        bundle = access.create_bundle(name, grants)
                    else:
                        access.change_bundle(bundle, name=name, grants=grants)
                except (AccessRefused, ValidationError) as error:
                    errors = _messages_of(error)
                else:
                    messages.success(request, _('The bundle %(name)s was saved.') % {'name': name})
                    return self.redirect('clearance_bundle', bundle.pk)

        holders = list(bundle.user_set.order_by('pk')) if bundle is not None else []
        return self.render(
            request,
            'bundle',
            bundle.name if bundle is not None else _('Add a bundle'),
            bundle=bundle,
            name=name,
            grid=PermissionGrid.build(grants),
            holders=holders,
            errors=errors,
            declared=bundle is not None and Declared.holds('bundle', bundle.name),
        )

    def delete_bundle(self, request: HttpRequest, pk: int) -> HttpResponse:
        self.require(request, 'view')
        bundle = get_object_or_404(Group, pk=pk)

        if request.method == 'POST':
            try:
                AccessService(actor=user_of(request)).delete_bundle(bundle)
            except AccessRefused as error:
                messages.error(request, str(error))
                return self.redirect('clearance_bundle', pk)

            messages.success(request, _('The bundle %(name)s was deleted.') % {'name': bundle.name})
            return self.redirect('clearance_bundles')

        holders = list(bundle.user_set.order_by('pk'))
        return self.render(
            request,
            'bundle_delete',
            _('Delete %(name)s') % {'name': bundle.name},
            bundle=bundle,
            holders=holders,
        )

    def people(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        query = request.GET.get('q', '').strip()
        people = get_user_model().objects.all()
        people = _matching(people, query) if query else _with_access(people)
        people = people.annotate(bundles=Count('groups', distinct=True)).order_by('pk')
        page = Paginator(people, PEOPLE_PER_PAGE).get_page(request.GET.get('page'))
        return self.render(request, 'people', _('People'), page=page, query=query)

    def person(self, request: HttpRequest, pk: int) -> HttpResponse:
        self.require(request, 'view')
        person = get_object_or_404(get_user_model(), pk=pk)

        if request.method == 'POST':
            self._change_person(request, person)
            return self.redirect('clearance_person', pk)

        standing = Standing.of(person)
        held = {bundle.pk for bundle in standing.bundles}
        return self.render(
            request,
            'person',
            str(person),
            person=person,
            standing=standing,
            other_bundles=Group.objects.exclude(pk__in=held).order_by('name'),
            all_permissions=[
                name_of(permission)
                for permission in Permission.objects.select_related('content_type').order_by(
                    'content_type__app_label', 'codename'
                )
            ],
        )

    def permissions(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        nobody = request.GET.get('held') == 'nobody'
        found = (
            Permission.objects.select_related('content_type')
            .annotate(people=Count('user', distinct=True))
            .prefetch_related('group_set')
            .order_by('content_type__app_label', 'content_type__model', 'codename')
        )

        if nobody:
            found = found.filter(group__isnull=True, user__isnull=True)

        taken = dict(
            PermissionRevocation.objects.values('permission')
            .annotate(count=Count('pk'))
            .values_list('permission', 'count')
        )
        permissions = list(found)

        for permission in permissions:
            permission.taken = taken.get(permission.pk, 0)  # type: ignore[attr-defined]

        return self.render(
            request, 'permissions', _('Permissions'), permissions=permissions, nobody=nobody
        )

    def _change_person(self, request: HttpRequest, person: Any) -> None:
        """One change to a person's access, from the person page; the service decides."""
        access, data, done = AccessService(actor=user_of(request)), request.POST, ''

        try:
            match data.get('do'):
                case 'give':
                    access.give_bundle(person, get_object_or_404(Group, pk=data.get('bundle')))
                    done = _('The bundle was given.')
                case 'take':
                    access.take_bundle(person, get_object_or_404(Group, pk=data.get('bundle')))
                    done = _('The bundle was taken back.')
                case 'grant':
                    access.grant(person, data.get('permission', ''), data.get('scope') or None)
                    done = _('The permission was given.')
                case 'revoke':
                    access.revoke(person, data.get('permission', ''), reason=data.get('reason', ''))
                    done = _('The permission was taken away.')
                case 'restore':
                    access.restore(person, data.get('permission', ''))
                    done = _('The permission was given back.')
                case _:
                    messages.error(request, _('Nothing was asked for.'))
                    return
        except (AccessRefused, ValidationError) as error:
            for message in _messages_of(error):
                messages.error(request, message)
            return

        messages.success(request, done)

    @staticmethod
    def _bundle_errors(name: str, bundle: Group | None) -> list[str]:
        if not name:
            return [_('A bundle needs a name.')]

        own: Any = getattr(bundle, 'pk', None)
        taken = Group.objects.filter(name=name).exclude(pk=own)
        return [_('There is a bundle called %(name)s already.') % {'name': name}] if taken else []


def _with_access(people: Any) -> Any:
    """The people with any access at all: a bundle, a grant of their own, or every permission."""
    return people.filter(
        Q(groups__isnull=False) | Q(user_permissions__isnull=False) | Q(is_superuser=True)
    ).distinct()


def _matching(people: Any, query: str) -> Any:
    """The people whose name, or e-mail address, has ``query`` in it."""
    model = people.model
    names = [model.USERNAME_FIELD, 'first_name', 'last_name', 'email']
    present = {field.name for field in model._meta.get_fields()}
    found = Q()

    for name in (name for name in names if name in present):
        found |= Q(**{f'{name}__icontains': query})

    return people.filter(found)


def _messages_of(error: AccessRefused | ValidationError) -> list[str]:
    return list(error.messages) if isinstance(error, ValidationError) else [str(error)]
