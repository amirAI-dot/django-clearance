"""
Misconfiguration found at start-up, by ``manage.py check`` and every
``runserver``, rather than by a person refused - or let in - in production.

Each check is two parts: a function of what it inspects, which the tests call
with exactly the classes they mean to, and a registered check that gathers
those things from the running project.

==================  =========================================================
``clearance.E001``  ``ROLES`` is missing while something scopes rows, or is
                    not valid
``clearance.E002``  a queryset has ``scope_for_<x>`` for a role nobody declared
``clearance.E004``  a scoped view's queryset is not a ``ScopedQuerySet``
``clearance.E005``  ``EVERY_ROW_ROLES`` names a role nobody declared
``clearance.E009``  a ``PolicyRequiredMixin`` view cannot ask its policy
``clearance.E010``  ``ROLE_RESOLVER`` or ``ROLE_ATTRIBUTE`` is not usable
``clearance.E011``  ``CLEARANCE`` is not a dictionary, or has an unknown key
==================  =========================================================
"""

from collections.abc import Iterable, Iterator
from typing import Any

from django.apps import apps
from django.core.checks import CheckMessage, Error
from django.core.exceptions import ImproperlyConfigured
from django.urls import URLPattern, URLResolver, get_resolver

from clearance.conf import clearance_settings
from clearance.querysets import ScopedQuerySet
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin

# ---------------------------------------------------------------------- settings


def settings_errors(*, rows_are_scoped: bool) -> list[CheckMessage]:
    """E011, E001, E005 and E010: whether the ``CLEARANCE`` setting can be used."""
    try:
        clearance_settings.raw()
    except ImproperlyConfigured as error:
        return [Error(str(error), id='clearance.E011')]

    errors: list[CheckMessage] = []

    if clearance_settings.roles_declared or rows_are_scoped:
        errors += _attempt(lambda: clearance_settings.roles, 'clearance.E001')

    if not errors and clearance_settings.roles_declared:
        errors += _attempt(lambda: clearance_settings.every_row_roles, 'clearance.E005')

    errors += _attempt(lambda: clearance_settings.role_resolver, 'clearance.E010')
    errors += _attempt(lambda: clearance_settings.role_attribute, 'clearance.E010')
    return errors


def check_settings(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return settings_errors(rows_are_scoped=bool(scoped_querysets()))


# ---------------------------------------------------------------------- querysets


def scope_hook_errors(
    querysets: Iterable[type[ScopedQuerySet[Any]]], roles: Iterable[str]
) -> list[CheckMessage]:
    """E002: a hook for a role nobody declared is a typo that silently denies."""
    declared = set(roles)
    errors: list[CheckMessage] = []

    for queryset in querysets:
        prefix = queryset.scope_prefix

        for name in sorted(dir(queryset)):
            role = name.removeprefix(prefix)

            if name.startswith(prefix) and role not in declared:
                errors.append(
                    Error(
                        f'{queryset.__name__}.{name}() is for the role {role!r}, which '
                        f"CLEARANCE['ROLES'] does not declare - so it is never asked.",
                        hint=f'Declared roles: {", ".join(sorted(declared)) or "none"}.',
                        obj=queryset,
                        id='clearance.E002',
                    )
                )

    return errors


def check_scope_hooks(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    querysets = scoped_querysets()

    if not querysets:
        return []

    try:
        roles = clearance_settings.roles
    except ImproperlyConfigured:
        return []  # E001 says so already.

    return scope_hook_errors(querysets, roles)


def scoped_querysets() -> list[type[ScopedQuerySet[Any]]]:
    """Every ``ScopedQuerySet`` a model in the project is managed with."""
    found: dict[type, None] = {}

    for model in apps.get_models():
        for manager in model._meta.managers:
            queryset = getattr(manager, '_queryset_class', None)

            if isinstance(queryset, type) and issubclass(queryset, ScopedQuerySet):
                found[queryset] = None

    return list(found)


# ---------------------------------------------------------------------- views


def view_errors(views: Iterable[type]) -> list[CheckMessage]:
    """E004 and E009: views that would show every row, or cannot ask their policy."""
    errors: list[CheckMessage] = []

    for view in views:
        if issubclass(view, ScopedQuerySetMixin):
            queryset = _declared_queryset(view)

            if queryset is not None and not isinstance(queryset, ScopedQuerySet):
                errors.append(
                    Error(
                        f'{view.__name__} uses ScopedQuerySetMixin, but its queryset is a '
                        f'{type(queryset).__name__} - so it shows every row to everybody.',
                        hint='Manage the model with a ScopedQuerySet.',
                        obj=view,
                        id='clearance.E004',
                    )
                )

        if issubclass(view, PolicyRequiredMixin):
            errors += [
                Error(message, obj=view, id='clearance.E009')
                for message in view.configuration_errors()
            ]

    return errors


def check_views(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    try:
        patterns = get_resolver().url_patterns
    except Exception:
        # A URLconf that does not import is Django's own check to report.
        return []

    return view_errors(dict.fromkeys(_view_classes(patterns)))


def _view_classes(patterns: Iterable[URLPattern | URLResolver]) -> Iterator[type]:
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from _view_classes(pattern.url_patterns)
            continue

        view_class = getattr(pattern.callback, 'view_class', None)

        if isinstance(view_class, type):
            yield view_class


def _declared_queryset(view: type) -> object:
    """What the view declares to list, without running it - or ``None``."""
    queryset = getattr(view, 'queryset', None)

    if queryset is not None:
        return queryset

    model = getattr(view, 'model', None)
    return model._default_manager.all() if model is not None else None


# ---------------------------------------------------------------------- helpers


def _attempt(read: Any, check_id: str) -> list[CheckMessage]:
    try:
        read()
    except ImproperlyConfigured as error:
        return [Error(str(error), id=check_id)]
    return []


#: Every check the core registers, in the order they run.
CHECKS = (check_settings, check_scope_hooks, check_views)
