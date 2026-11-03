"""
The Django application that plugs the library into a project.

Listing ``'clearance'`` in ``INSTALLED_APPS`` is what lets Django find the
library's system checks and its translations. The core has no models, so
installing it adds no table and no migration.
"""

from django.apps import AppConfig


class ClearanceConfig(AppConfig):
    name = 'clearance'
    label = 'clearance'

    # A product name, the same in every language - so not marked for translation.
    verbose_name = 'Clearance'
