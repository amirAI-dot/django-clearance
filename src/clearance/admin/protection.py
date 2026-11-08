"""
The protected fields pages: each model's fields, which are protected - in
code, or here - and the two permissions of each.

Protecting and unprotecting go through ``AccessService``: a field a rule
reads is not protected, a field protected in code is unprotected in code,
and nobody unprotects a field they were never given.
"""

from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path
from django.utils.translation import gettext as _

from clearance.admin.views import PageSet
from clearance.fields import Protection, field_names, field_permissions, protection_problem
from clearance.permissions import declared_protected_fields
from clearance.protocols import user_of
from clearance.safety import AccessRefused
from clearance.services import AccessService


class FieldPages(PageSet):
    def get_urls(self) -> list[URLPattern]:
        wrap = self.site.admin_view
        return [
            path('fields/', wrap(self.models_page), name='clearance_fields'),
            path('fields/<str:label>/', wrap(self.model_page), name='clearance_fields_of'),
        ]

    def menu(self, request: HttpRequest) -> list[dict[str, Any]]:
        return [
            {
                'name': _('Protected fields'),
                'object_name': 'ProtectedField',
                'admin_url': self.url('clearance_fields'),
                'add_url': None,
                'view_only': not self.may(request, 'edit'),
            }
        ]

    def models_page(self, request: HttpRequest) -> HttpResponse:
        self.require(request, 'view')
        protection = Protection.load()
        rows = [
            (label, words, len(protection.fields(self.model_named(label))))
            for label, words in self.models()
        ]
        return self.render(request, 'fields', _('Protected fields'), rows=rows)

    def model_page(self, request: HttpRequest, label: str) -> HttpResponse:
        self.require(request, 'view')
        model = self.model_named(label)

        if request.method == 'POST':
            self._change(request, model, request.POST.get('field', ''))
            return self.redirect('clearance_fields_of', label)

        protection = Protection.load()
        in_code = set(declared_protected_fields(model))
        fields = [
            {
                'name': name,
                'words': str(getattr(model._meta.get_field(name), 'verbose_name', name)),
                'in_code': name in in_code,
                'protected': protection.protects(model, name),
                'permissions': field_permissions(model, name),
                'cannot': protection_problem(model, name),
            }
            for name in field_names(model)
        ]
        return self.render(
            request, 'fields_of', str(model._meta.verbose_name_plural), model=model, fields=fields
        )

    def _change(self, request: HttpRequest, model: Any, field: str) -> None:
        access = AccessService(actor=user_of(request))

        try:
            if request.POST.get('do') == 'protect':
                access.protect_field(model, field)
                messages.success(request, _('%(field)s is protected.') % {'field': field})
            else:
                access.unprotect_field(model, field)
                messages.success(request, _('%(field)s is no longer protected.') % {'field': field})
        except (AccessRefused, ValidationError) as error:
            for message in error.messages if isinstance(error, ValidationError) else [str(error)]:
                messages.error(request, message)
