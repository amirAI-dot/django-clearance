"""
Names in every language: ``INSTALLED_APPS += ['clearance.translations']``, after
``'clearance'``.

Starting the app puts its labels in force (``clearance.labels``), so every
page naming a permission, a bundle or a role names it in the reader's
language, and removes a name with the thing it names.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TranslationsConfig(AppConfig):
    name = 'clearance.translations'
    label = 'clearance_translations'
    default_auto_field = 'django.db.models.BigAutoField'

    # A product name, the same in every language - so not marked for translation.
    verbose_name = _('Clearance: translations')

    def ready(self) -> None:
        from django.core.checks import register
        from django.db.models.signals import post_delete

        from clearance.labels import install_labels
        from clearance.translations.checks import CHECKS
        from clearance.translations.labels import TranslatedLabels, forget_names

        for check in CHECKS:
            register(check, 'clearance')

        install_labels(TranslatedLabels)
        post_delete.connect(forget_names, dispatch_uid='clearance.translations.forget_names')
