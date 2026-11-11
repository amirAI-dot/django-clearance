"""
Naming a permission, a bundle or a role in a language - under the library's
own permission to edit access, because a name is what an administrator reads
when they choose what to give.

    TranslationService(actor=request.user).name(bundle, 'fa', name_in_persian)

A language is one of ``LANGUAGES``; an empty name takes the name in that
language away.
"""

from typing import Any

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from clearance.protocols import User
from clearance.safety import SafetyRules
from clearance.translations import signals
from clearance.translations.models import Translation


class TranslationService:
    def __init__(self, actor: User | None) -> None:
        self.actor = actor
        self.rules = SafetyRules(actor)

    def name(self, thing: Any, language: str, name: str, description: str = '') -> None:
        """Name ``thing`` in ``language`` - or, with no name, stop naming it there."""
        self.rules.require_may('edit')
        known = [code for code, _ in settings.LANGUAGES]

        if language not in known:
            raise ValidationError(f'{language!r} is not one of LANGUAGES: {", ".join(known)}.')

        where: dict[str, Any] = {
            'content_type': ContentType.objects.get_for_model(thing),
            'object_pk': str(thing.pk),
            'language': language,
        }
        row = Translation.objects.filter(**where).first()
        before = (row.name, row.description) if row is not None else None
        name, description = name.strip(), description.strip()
        after = (name, description) if name else None

        if before == after:
            return

        if after is None:
            Translation.objects.filter(**where).delete()
        else:
            Translation.objects.update_or_create(
                **where, defaults={'name': name, 'description': description}
            )

        def send() -> None:
            signals.name_changed.send(
                sender=TranslationService,
                actor=self.actor,
                thing=thing,
                language=language,
                before=before,
                after=after,
            )

        transaction.on_commit(send)
