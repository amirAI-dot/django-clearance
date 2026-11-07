"""
Roles, checked at start-up.

==================  =========================================================
``clearance.E008``  ``clearance.roles`` is installed without ``'clearance'``,
                    or before it
``clearance.E010``  ``ROLE_RESOLVER`` cannot be used, or ``AttributeResolver``
                    is asked to read a field the user model does not have
==================  =========================================================
"""

from collections.abc import Sequence
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.checks import CheckMessage, Error
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured


def order_errors(labels: Sequence[str]) -> list[CheckMessage]:
    """E008: the core is installed, and before the roles."""
    core, roles = 'clearance', 'clearance_roles'

    if roles in labels and (core not in labels or labels.index(core) > labels.index(roles)):
        return [
            Error(
                "'clearance.roles' needs 'clearance' installed, and listed before it.",
                hint="List 'clearance' before 'clearance.roles' in INSTALLED_APPS.",
                id='clearance.E008',
            )
        ]

    return []


def resolver_errors() -> list[CheckMessage]:
    """E010: the resolver can be made, and an attribute it reads is a field."""
    from clearance.roles.resolvers import AttributeResolver, resolver

    try:
        found = resolver()
    except (ImportError, ImproperlyConfigured) as error:
        return [Error(f"CLEARANCE['ROLE_RESOLVER'] cannot be used: {error}", id='clearance.E010')]

    if isinstance(found, AttributeResolver):
        try:
            get_user_model()._meta.get_field(found.attribute)
        except FieldDoesNotExist:
            return [
                Error(
                    f"CLEARANCE['ROLE_ATTRIBUTE'] is {found.attribute!r}, which is not a field "
                    f'of {get_user_model().__name__}: roles are read in the query, from a column.',
                    id='clearance.E010',
                )
            ]

    return []


def check_order(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return order_errors([config.label for config in apps.get_app_configs()])


def check_resolver(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return resolver_errors()


#: Every roles check, registered by the app.
CHECKS = (check_order, check_resolver)
