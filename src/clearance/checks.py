"""
Misconfiguration found at start-up, by ``manage.py check`` and every
``runserver``, rather than by a person refused - or let in - in production.

Each check is two parts: a function of what it inspects, which the tests call
with exactly what they mean to, and a registered check that gathers those
things from the running project.

==================  =========================================================
``clearance.E002``  a queryset's ``scopes`` and its ``scope_<x>`` methods
                    disagree, or its ``default_scope`` is not offered
``clearance.E004``  a scoped view's queryset is not a ``ScopedQuerySet``
``clearance.E006``  ``ClearanceBackend`` is not installed
``clearance.E007``  ``ModelBackend`` is installed beside it
``clearance.E009``  a ``PolicyRequiredMixin`` view cannot ask a policy
``clearance.E011``  ``CLEARANCE`` is not a dictionary, or has an unknown key
``clearance.E014``  a model declares its own permissions but keeps Django's
==================  =========================================================
"""

from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.checks import CheckMessage, Error
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.urls import URLPattern, URLResolver, get_resolver

from clearance.conf import clearance_settings
from clearance.querysets import EVERY_ROW, ScopedQuerySet
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin

BACKEND = 'clearance.backends.ClearanceBackend'
MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'

#: The actions whose codenames say a model declares its own permissions.
_OWN_ACTIONS = ('_view', '_create', '_edit', '_delete')

# ---------------------------------------------------------------------- settings


def check_settings(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """E011: the ``CLEARANCE`` setting can be read."""
    try:
        clearance_settings.raw()
    except ImproperlyConfigured as error:
        return [Error(str(error), id='clearance.E011')]
    return []


def backend_errors(backends: Sequence[str]) -> list[CheckMessage]:
    """E006 and E007: revocations and scopes need ``ClearanceBackend``, alone."""
    if BACKEND not in backends:
        return [
            Error(
                f'{BACKEND} is not in AUTHENTICATION_BACKENDS, so revocations and scopes '
                f'would silently do nothing.',
                hint=f'Put {BACKEND!r} in place of {MODEL_BACKEND!r}.',
                id='clearance.E006',
            )
        ]

    if MODEL_BACKEND in backends:
        return [
            Error(
                f'{MODEL_BACKEND} is beside {BACKEND}. Django grants a permission when any '
                f'backend does, so it would hand back every permission taken away.',
                hint=f'Remove {MODEL_BACKEND!r}: {BACKEND} does all it did.',
                id='clearance.E007',
            )
        ]

    return []


def check_backends(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return backend_errors(list(settings.AUTHENTICATION_BACKENDS))


# ---------------------------------------------------------------------- models


def permission_errors(models: Iterable[type[Model]]) -> list[CheckMessage]:
    """E014: a model declaring its own permissions turns Django's off."""
    errors: list[CheckMessage] = []

    for model in models:
        meta = model._meta
        own = [codename for codename, _ in meta.permissions if codename.endswith(_OWN_ACTIONS)]

        if own and meta.default_permissions:
            errors.append(
                Error(
                    f'{meta.label} declares its own permissions ({", ".join(own)}) and keeps '
                    f"Django's ({', '.join(meta.default_permissions)}): the admin site would "
                    f'offer permissions nothing checks.',
                    hint='Add default_permissions = () to its Meta.',
                    obj=model,
                    id='clearance.E014',
                )
            )

    return errors


def check_models(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return permission_errors(apps.get_models())


def scope_errors(querysets: Iterable[type[ScopedQuerySet[Any]]]) -> list[CheckMessage]:
    """E002: every scope offered has its method, every method is offered, the default exists."""
    errors: list[CheckMessage] = []

    for queryset in querysets:
        prefix = queryset.hook_prefix
        declared = set(queryset.scopes)
        methods = {
            name.removeprefix(prefix)
            for name in dir(queryset)
            if name.startswith(prefix) and callable(getattr(queryset, name))
        }

        problems = [
            *(
                f'scopes offers {name!r} with no {prefix}{name}()'
                for name in sorted(declared - methods)
            ),
            *(
                f'{prefix}{name}() is not in scopes, so nobody can choose it'
                for name in sorted(methods - declared)
            ),
        ]

        if EVERY_ROW in declared:
            problems.append(f'{EVERY_ROW!r} is offered by every queryset and cannot be redefined')

        default = queryset.default_scope

        if default is not None and default != EVERY_ROW and default not in declared:
            problems.append(f'default_scope {default!r} is not a scope it offers')

        errors += [
            Error(f'{queryset.__name__}: {problem}.', obj=queryset, id='clearance.E002')
            for problem in problems
        ]

    return errors


def check_scopes(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return scope_errors(scoped_querysets())


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
    """E004 and E009: views that would show every row, or cannot ask a policy."""
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


#: Every check the core registers, in the order they run.
CHECKS = (check_settings, check_backends, check_models, check_scopes, check_views)
