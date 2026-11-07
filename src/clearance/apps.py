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

    #: The library's own tables, whatever DEFAULT_AUTO_FIELD a project sets - or its
    #: migrations would differ from every project's models but the one that made them.
    default_auto_field = 'django.db.models.BigAutoField'

    # A product name, the same in every language - so not marked for translation.
    verbose_name = 'Clearance'

    def ready(self) -> None:
        from django.apps import apps
        from django.core.checks import register
        from django.db.models.signals import post_migrate

        from clearance.checks import CHECKS
        from clearance.discovery import make_permissions_after_migrate

        for check in CHECKS:
            register(check, 'clearance')

        if apps.is_installed('rest_framework'):
            from clearance.drf.checks import CHECKS as API_CHECKS  # DRF is optional

            for check in API_CHECKS:
                register(check, 'clearance')

        if apps.is_installed('django.contrib.admin'):
            from clearance.admin.checks import CHECKS as ADMIN_CHECKS  # the admin is optional

            for check in ADMIN_CHECKS:
                register(check, 'clearance')

        post_migrate.connect(make_permissions_after_migrate, sender=self)
