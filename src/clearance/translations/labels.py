"""
Names an administrator gave, in force when the app starts.

A thing reads its name in the reader's language - ``fa``, or ``fa`` for
``fa-ir`` - and otherwise as the code or its row says it. The names of one
language are read once, in one query, the first time a page asks.
"""

from typing import Any

from django.contrib.contenttypes.models import ContentType

from clearance.labels import Labels
from clearance.translations.models import Translation

#: What a name is kept under: ``(content type id, object pk)``.
Key = tuple[int, str]


class TranslatedLabels(Labels):
    def __init__(self, language: str) -> None:
        super().__init__(language)
        self._names: dict[Key, tuple[str, str]] | None = None

    def of(self, thing: Any) -> str:
        found = self._found(thing)
        return found[0] if found is not None else super().of(thing)

    def description_of(self, thing: Any) -> str:
        found = self._found(thing)
        return found[1] if found is not None else ''

    def _found(self, thing: Any) -> tuple[str, str] | None:
        pk = getattr(thing, 'pk', None)

        if pk is None:
            return None

        key = (ContentType.objects.get_for_model(thing).pk, str(pk))
        return self._loaded().get(key)

    def _loaded(self) -> dict[Key, tuple[str, str]]:
        """Every name in the language - its exact code first, then its base."""
        if self._names is None:
            languages = languages_for(self.language)
            rows = Translation.objects.filter(language__in=languages).values_list(
                'content_type_id', 'object_pk', 'language', 'name', 'description'
            )
            names: dict[Key, tuple[str, str]] = {}

            for content_type, pk, _language, name, description in sorted(
                rows, key=lambda row: languages.index(row[2]), reverse=True
            ):
                names[(content_type, pk)] = (name, description)

            self._names = names

        return self._names


def languages_for(language: str) -> list[str]:
    """``fa-ir`` reads ``fa-ir``, then ``fa``."""
    base = language.split('-')[0]
    return [language, base] if base != language else [language]


def forget_names(sender: Any, instance: Any, **kwargs: Any) -> None:
    """``post_delete``: a name goes with the thing it names."""
    if sender is Translation:
        return

    content_type = ContentType.objects.get_for_model(sender)
    Translation.objects.filter(content_type=content_type, object_pk=str(instance.pk)).delete()
