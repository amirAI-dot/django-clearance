"""
The Django application that plugs the library into a project.

Listing ``'clearance'`` in ``INSTALLED_APPS`` is what lets Django find the
library's system checks and its translations, and what makes ``migrate``
make the permission of every action found in the code.
"""

from django.apps import AppConfig


class ClearanceConfig(AppConfig):
    name = 'clearance'
    label = 'clearance'

    # A product name, the same in every language - so not marked for translation.
    verbose_name = 'Clearance'

    def ready(self) -> None:
        from django.core.checks import register
        from django.db.models.signals import post_migrate

        from clearance.checks import CHECKS
        from clearance.discovery import make_permissions_after_migrate

        for check in CHECKS:
            register(check, 'clearance')

        post_migrate.connect(make_permissions_after_migrate, sender=self)
