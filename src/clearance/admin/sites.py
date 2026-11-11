"""
The library's admin site: Django's own, asking the library.

A project uses it by naming the library's admin app in ``INSTALLED_APPS`` in
place of Django's - nothing else in the project changes::

    INSTALLED_APPS = [
        'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
        ...
    ]

Every ``ModelAdmin`` registered on it gets the library's hooks
(``clearance.admin.options``), and it adds the access pages under ``access/``.
A project with an admin site of its own subclasses this one.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.urls import URLPattern, URLResolver, include, path, reverse
from django.utils.translation import gettext as _

from clearance.admin.options import protected_admin
from clearance.admin.views import AccessPages


class ClearanceAdminSite(admin.AdminSite):
    """Django's admin site, every page asking the library, with the access pages added."""

    def register(
        self,
        model_or_iterable: Any,
        admin_class: type[Any] | None = None,
        **options: Any,
    ) -> None:
        chosen: Any = admin_class or admin.ModelAdmin
        super().register(model_or_iterable, protected_admin(chosen), **options)

    def get_urls(self) -> list[URLPattern | URLResolver]:
        pages = AccessPages(self)
        return [path('access/', include(pages.get_urls())), *super().get_urls()]

    def get_app_list(self, request: HttpRequest, app_label: str | None = None) -> list[Any]:
        listed: list[Any] = super().get_app_list(request, app_label)
        pages = AccessPages(self)

        if app_label in (None, 'clearance') and pages.may(request, 'view'):
            listed.append(self._access_app(request, pages))

        return listed

    def _access_app(self, request: HttpRequest, pages: AccessPages) -> dict[str, Any]:
        def url(name: str) -> str:
            return reverse(f'{self.name}:{name}', current_app=self.name)

        view_only = not pages.may(request, 'edit')
        return {
            'name': _('Access'),
            'app_label': 'clearance',
            'app_url': url('clearance_overview'),
            'has_module_perms': True,
            'models': [
                {
                    'name': _('Bundles'),
                    'object_name': 'Bundle',
                    'admin_url': url('clearance_bundles'),
                    'add_url': url('clearance_bundle_add')
                    if pages.may(request, 'create')
                    else None,
                    'view_only': view_only,
                },
                {
                    'name': _('People'),
                    'object_name': 'Person',
                    'admin_url': url('clearance_people'),
                    'add_url': None,
                    'view_only': view_only,
                },
                {
                    'name': _('Permissions'),
                    'object_name': 'Permission',
                    'admin_url': url('clearance_permissions'),
                    'add_url': None,
                    'view_only': True,
                },
            ],
        }
