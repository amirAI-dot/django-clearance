"""
The names page of the admin site: a permission, a bundle or a role, named in
every language of ``LANGUAGES`` - linked from each one's own page.
"""

from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import URLPattern, path
from django.utils.translation import gettext as _

from clearance.admin.views import PageSet
from clearance.labels import Labels
from clearance.protocols import user_of
from clearance.safety import AccessRefused
from clearance.translations.models import Translation
from clearance.translations.services import TranslationService

#: What may be named here, by the content type's ``app_label.model``.
NAMEABLE = ('auth.permission', 'auth.group', 'clearance_roles.role')


class NamePages(PageSet):
    template_dir = 'clearance/translations'

    def get_urls(self) -> list[URLPattern]:
        return [
            path(
                'names/<str:kind>/<str:pk>/',
                self.site.admin_view(self.names),
                name='clearance_names',
            )
        ]

    def names(self, request: HttpRequest, kind: str, pk: str) -> HttpResponse:
        self.require(request, 'view')
        thing = _thing(kind, pk)

        if request.method == 'POST':
            service = TranslationService(actor=user_of(request))

            try:
                for language, _words in settings.LANGUAGES:
                    service.name(
                        thing,
                        language,
                        request.POST.get(f'name:{language}', ''),
                        request.POST.get(f'description:{language}', ''),
                    )
            except (AccessRefused, ValidationError) as error:
                for message in (
                    error.messages if isinstance(error, ValidationError) else [str(error)]
                ):
                    messages.error(request, message)
            else:
                messages.success(request, _('The names were saved.'))

            return self.redirect('clearance_names', kind, pk)

        given = {
            row.language: row
            for row in Translation.objects.filter(
                content_type=ContentType.objects.get_for_model(thing), object_pk=str(thing.pk)
            )
        }
        return self.render(
            request,
            'names',
            _('Names of %(thing)s') % {'thing': Labels.stored(thing)},
            thing=thing,
            stored=Labels.stored(thing),
            rows=[(code, words, given.get(code)) for code, words in settings.LANGUAGES],
        )


def _thing(kind: str, pk: str) -> Any:
    if kind not in NAMEABLE:
        raise Http404(kind)

    app_label, _, model = kind.partition('.')

    try:
        content_type = ContentType.objects.get(app_label=app_label, model=model)
        found = content_type.get_object_for_this_type(pk=pk)
    except (ObjectDoesNotExist, ValueError, ValidationError):
        raise Http404(f'{kind} {pk}') from None

    return found
