"""
Translations, checked at start-up.

==================  =========================================================
``clearance.E008``  ``clearance.translations`` is installed without
                    ``'clearance'``, or before it
==================  =========================================================
"""

from collections.abc import Sequence
from typing import Any

from django.apps import apps
from django.core.checks import CheckMessage, Error


def order_errors(labels: Sequence[str]) -> list[CheckMessage]:
    core, translations = 'clearance', 'clearance_translations'

    if translations in labels and (
        core not in labels or labels.index(core) > labels.index(translations)
    ):
        return [
            Error(
                "'clearance.translations' needs 'clearance' installed, and listed before it.",
                hint="List 'clearance' before 'clearance.translations' in INSTALLED_APPS.",
                id='clearance.E008',
            )
        ]

    return []


def check_order(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return order_errors([config.label for config in apps.get_app_configs()])


CHECKS = (check_order,)
