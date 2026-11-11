"""
How a permission, a bundle or a role reads - in the reader's language.

    label_of(permission)                 # 'Can approve or decline loans', or its Persian
    labels = labels_in('fa')             # for a page naming many things: one query at most
    labels.of(bundle), labels.description_of(bundle)

Without ``clearance.translations`` a permission declared with
``build_permissions`` reads its label in the active language - the project's
own catalogue translates it - and anything else reads its stored name. With
it installed, a name an administrator gave in a language comes first; its
app puts its own labels in force when it starts, so the core never imports
it.
"""

from typing import Any

from django.conf import settings
from django.contrib.auth.models import Permission
from django.utils import translation

from clearance.permissions import declared_label


class Labels:
    """Names as the code and the database give them: no translations kept apart."""

    def __init__(self, language: str) -> None:
        self.language = language

    def of(self, thing: Any) -> str:
        """How ``thing`` reads."""
        with translation.override(self.language):
            return self.stored(thing)

    def description_of(self, thing: Any) -> str:
        """What ``thing`` is for - nothing, unless somebody wrote it down."""
        return ''

    @staticmethod
    def stored(thing: Any) -> str:
        """What the code or the row says, in the active language where the code says it."""
        if isinstance(thing, Permission):
            model = thing.content_type.model_class()
            declared = declared_label(model, thing.codename) if model is not None else None
            return declared or str(thing.name)
        return str(getattr(thing, 'name', thing))


_source: type[Labels] = Labels


def labels_in(language: str | None = None) -> Labels:
    """The names in ``language`` - the active one when left out."""
    return _source(language or translation.get_language() or settings.LANGUAGE_CODE)


def label_of(thing: Any, language: str | None = None) -> str:
    """How ``thing`` reads in ``language``."""
    return labels_in(language).of(thing)


def install_labels(source: type[Labels]) -> None:
    """Put ``source`` in force - called by ``clearance.translations`` when it starts."""
    global _source
    _source = source


def uninstall_labels() -> None:
    install_labels(Labels)
