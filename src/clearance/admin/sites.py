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

from typing import Any, ClassVar

from django.contrib import admin
from django.http import HttpRequest
from django.urls import URLPattern, URLResolver, include, path
from django.utils.translation import gettext as _

from clearance.admin.options import protected_admin
from clearance.admin.views import AccessPages, PageSet


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

    #: The sets of access pages every site mounts. ``add_pages`` adds one.
    page_sets: ClassVar[list[type[PageSet]]] = [AccessPages]

    @classmethod
    def add_pages(cls, pages: type[PageSet]) -> None:
        """Mount ``pages`` beside the access pages, on every site - once."""
        if pages not in cls.page_sets:
            cls.page_sets.append(pages)

    def get_urls(self) -> list[URLPattern | URLResolver]:
        urls = [url for pages in self.page_sets for url in pages(self).get_urls()]
        return [path('access/', include(urls)), *super().get_urls()]

    def get_app_list(self, request: HttpRequest, app_label: str | None = None) -> list[Any]:
        listed: list[Any] = super().get_app_list(request, app_label)
        overview = AccessPages(self)

        if app_label in (None, 'clearance') and overview.may(request, 'view'):
            listed.append(
                {
                    'name': _('Access'),
                    'app_label': 'clearance',
                    'app_url': overview.url('clearance_overview'),
                    'has_module_perms': True,
                    'models': [
                        entry for pages in self.page_sets for entry in pages(self).menu(request)
                    ],
                }
            )

        return listed
