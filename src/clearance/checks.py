"""
Misconfiguration found at start-up, by ``manage.py check`` and every
``runserver``, rather than by a person refused - or let in - in production.

Each check is two parts: a function of what it inspects, which the tests call
with exactly what they mean to, and a registered check that gathers those
things from the running project.

==================  =========================================================
``clearance.E001``  the ``ACCESS`` file cannot be read, or says something that
                    cannot be
``clearance.E002``  a queryset's ``scopes`` and its ``scope_<x>`` methods
                    disagree, or its ``default_scope`` is not offered
``clearance.E006``  ``ClearanceBackend`` is not installed
``clearance.E007``  ``ModelBackend``, or a backend built on it, is installed
                    beside it
``clearance.E009``  a ``PolicyRequiredMixin`` view cannot ask a policy
``clearance.E011``  ``CLEARANCE`` is not a dictionary, has an unknown key, or a
                    value it cannot use
``clearance.E012``  a field protected in code is not a field of its model,
                    cannot be protected, or has a permission another model has
``clearance.E013``  an action found in the code cannot make a permission
``clearance.E014``  a model declares its own permissions but keeps Django's
``clearance.E015``  a status action declared in code names a field or a value
                    its model does not have
==================  =========================================================
"""

from collections.abc import Iterable, Sequence
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.checks import CheckMessage, Error
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model

from clearance.actions import status_action_problems
from clearance.conf import clearance_settings
from clearance.declared import access_problems, read_access
from clearance.discovery import FoundAction, action_problems, find_actions
from clearance.fields import field_permissions, protection_problem
from clearance.permissions import declared_protected_fields, declared_status_actions
from clearance.querysets import EVERY_ROW, ScopedQuerySet
from clearance.views import PolicyRequiredMixin, urlconf_callbacks

BACKEND = 'clearance.backends.ClearanceBackend'
MODEL_BACKEND = 'django.contrib.auth.backends.ModelBackend'

#: The actions whose codenames say a model declares its own permissions.
_OWN_ACTIONS = ('_view', '_create', '_edit', '_delete')

# ---------------------------------------------------------------------- settings


def check_settings(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """E011: the ``CLEARANCE`` setting can be read, and the fields it names exist."""
    try:
        clearance_settings.raw()
    except ImproperlyConfigured as error:
        return [Error(str(error), id='clearance.E011')]

    user = get_user_model()
    names = {field.name for field in user._meta.get_fields()}
    return [
        Error(
            f"CLEARANCE['PERSON_FIELDS'] names {name!r}, which is not a field of "
            f'{user._meta.label}.',
            id='clearance.E011',
        )
        for name in sorted(clearance_settings.person_fields() - names)
    ]


def check_access(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    """
    E001: the ``ACCESS`` file reads, and says nothing that cannot be. Whether
    the permissions and scopes it names exist is the database's to say:
    ``clearance_sync --check`` says it.
    """
    try:
        access = read_access()
    except ImproperlyConfigured as error:
        return [Error(str(error), id='clearance.E001')]

    if access is None:
        return []

    return [Error(f'ACCESS {problem}', id='clearance.E001') for problem in access_problems(access)]


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

    return [
        Error(
            f'{path} is beside {BACKEND}, and reads permissions as {MODEL_BACKEND} does. '
            f'Django grants a permission when any backend does, so it would hand back '
            f'every permission taken away.',
            hint=f'Remove {path!r}, or build it on {BACKEND}: that does all {MODEL_BACKEND} did.',
            id='clearance.E007',
        )
        for path in backends
        if _reads_as_model_backend(path)
    ]


def _reads_as_model_backend(path: str) -> bool:
    """
    Whether ``path`` is Django's ``ModelBackend`` or built on it - and not on
    the library's: it would answer from Django's tables alone, knowing nothing
    of a revocation, a ceiling or a starting bundle.
    """
    from django.contrib.auth.backends import ModelBackend
    from django.utils.module_loading import import_string

    from clearance.backends import ClearanceBackend

    try:
        backend = import_string(path)
    except ImportError:
        return False  # Django says so itself, the first time anybody signs in

    return (
        isinstance(backend, type)
        and issubclass(backend, ModelBackend)
        and not issubclass(backend, ClearanceBackend)
    )


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


def field_errors(models: Iterable[type[Model]]) -> list[CheckMessage]:
    """
    E012: every field a model protects in code can be protected - it is a
    field of the model, and its two permissions are no other model's.
    """
    models = list(models)
    errors: list[CheckMessage] = [
        Error(
            f'{model._meta.label} protects {name!r} in code, and cannot: {problem}',
            obj=model,
            id='clearance.E012',
        )
        for model in models
        for name in declared_protected_fields(model)
        if (problem := protection_problem(model, name)) is not None
    ]

    for model in models:
        if model._meta.proxy:
            continue  # its fields are its concrete model's, and so are their permissions

        for name in declared_protected_fields(model):
            for permission in field_permissions(model, name).values():
                for other in apps.get_app_config(model._meta.app_label).get_models():
                    if other is not model and permission in _own_permissions(other):
                        errors.append(
                            Error(
                                f'{model._meta.label} protects {name!r} with {permission}, which '
                                f'is a permission of {other._meta.label} too: holding that one '
                                f'would be holding this.',
                                hint='Rename the field, or the other permission.',
                                obj=model,
                                id='clearance.E012',
                            )
                        )

    return errors


def _own_permissions(model: type[Model]) -> set[str]:
    """What ``model`` itself declares, as ``app_label.codename`` - but its fields' own two."""
    meta = model._meta
    fields = {
        permission
        for name in declared_protected_fields(model)
        for permission in field_permissions(model, name).values()
    }
    declared = {f'{meta.app_label}.{codename}' for codename, _ in meta.permissions}
    standard = {f'{meta.app_label}.{verb}_{meta.model_name}' for verb in meta.default_permissions}
    return (declared | standard) - fields


def status_action_errors(models: Iterable[type[Model]]) -> list[CheckMessage]:
    """E015: every status action a model declares in code can work."""
    return [
        Error(
            f'{model._meta.label}, status action {code!r}: {problem}',
            obj=model,
            id='clearance.E015',
        )
        for model in models
        for code, spec in declared_status_actions(model).items()
        for problem in status_action_problems(model, code, spec['field'], spec['to'], spec['from'])
    ]


def check_models(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    models = apps.get_models()
    return [*permission_errors(models), *field_errors(models), *status_action_errors(models)]


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
    """E009: views that cannot ask a policy."""
    errors: list[CheckMessage] = []

    for view in views:
        if issubclass(view, PolicyRequiredMixin):
            errors += [
                Error(message, obj=view, id='clearance.E009')
                for message in view.configuration_errors()
            ]

    return errors


def check_views(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    try:
        callbacks = list(urlconf_callbacks())
    except Exception:
        # A URLconf that does not import is Django's own check to report.
        return []

    views = [getattr(callback, 'view_class', None) for callback in callbacks]
    return view_errors(dict.fromkeys(view for view in views if isinstance(view, type)))


# ---------------------------------------------------------------------- actions


def found_action_errors(found: Iterable[FoundAction]) -> list[CheckMessage]:
    """E013: every action found in the code can make its permission."""
    return [
        Error(problem, id='clearance.E013')
        for action in found
        if (problem := action_problems(action)) is not None
    ]


def check_actions(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    try:
        found = find_actions()
    except Exception:
        # A URLconf that does not import is Django's own check to report.
        return []

    return found_action_errors(found)


#: Every check the core registers, in the order they run.
CHECKS = (
    check_settings,
    check_access,
    check_backends,
    check_models,
    check_scopes,
    check_views,
    check_actions,
)
