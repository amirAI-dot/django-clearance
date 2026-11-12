"""
Which fields of a row a person may read, and which they may write.

A field is **protected** in code - ``build_permissions(..., protected_fields=
('price',))`` - or marked in the database by an administrator
(``AccessService.protect_field``). Either way it has two permissions:

* **view** - without it the field is left out, as if the model had none;
* **edit** - without it the field is shown but cannot be changed.

A field that may not be read may not be written either: a form offering it
would show what it holds. Every field nobody protected is read and written by
whoever may read and write the row - that is the policy's to say, not this
module's. The superuser reads and writes every field.

    readable_fields(user, Loan)     # frozenset({'applicant', 'amount', ...})
    writable_fields(user, Loan)

What is protected is read **once per request**, in one query over the whole
table, and kept on the user object beside their grants - the table holds the
handful of fields a project protects, not one row per person.
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model

from clearance.grants import KEPT_PREFIX, grants_of
from clearance.models import ProtectedField
from clearance.permissions import (
    FIELD_ACTIONS,
    declared_protected_fields,
    field_owner,
    field_permission,
    models_of,
)
from clearance.protocols import User

#: Where what is protected is kept on a user object once read.
_CACHE_ATTRIBUTE = f'{KEPT_PREFIX}protection'

#: A model, as the table of protected fields names it: ``(app_label, model_name)``.
ModelKey = tuple[str, str]


class Protection:
    """Every protected field as it stands: declared in code, or marked in the database."""

    def __init__(self, stored: Mapping[ModelKey, frozenset[str]]) -> None:
        self._stored = MappingProxyType(dict(stored))

    @classmethod
    def load(cls) -> 'Protection':
        """What the database marks protected, read in one query."""
        stored: dict[ModelKey, set[str]] = {}
        rows = ProtectedField.objects.values_list(
            'content_type__app_label', 'content_type__model', 'field'
        )

        for app_label, model_name, field in rows:
            stored.setdefault((app_label, model_name), set()).add(field)

        return cls({key: frozenset(fields) for key, fields in stored.items()})

    def fields(self, model: type[Model]) -> frozenset[str]:
        """The fields of ``model`` that are protected, wherever that was said."""
        return frozenset(declared_protected_fields(model)) | self.stored(model)

    def stored(self, model: type[Model]) -> frozenset[str]:
        """
        The fields of ``model`` an administrator protected in the database -
        on it, or on a parent it inherits them from.
        """
        found: frozenset[str] = frozenset()

        for owner in models_of(model):
            found |= self._stored.get(model_key(owner), frozenset())

        return found

    def protects(self, model: type[Model], name: str) -> bool:
        return name in self.fields(model)

    def owns(self, model: type[Model], permission: str) -> bool:
        """Whether ``permission`` - ``app_label.codename`` - is one of a protected field's."""
        return any(
            permission in field_permissions(model, name).values() for name in self.fields(model)
        )

    def adding(self, model: type[Model], name: str) -> 'Protection':
        """As it would be with ``model.name`` protected too - to see what that would break."""
        key = model_key(field_owner(model, name))
        return Protection({**self._stored, key: self._stored.get(key, frozenset()) | {name}})


def protection_of(user: object) -> Protection:
    """What is protected, read once for ``user``'s request and kept on them."""
    cached: Protection | None = getattr(user, _CACHE_ATTRIBUTE, None)

    if cached is None:
        cached = Protection.load()
        setattr(user, _CACHE_ATTRIBUTE, cached)

    return cached


def readable_fields(user: User, model: type[Model]) -> frozenset[str]:
    """The fields of ``model`` ``user`` may read: every field but the protected ones they lack."""
    return _allowed(user, model, ('view',))


def writable_fields(user: User, model: type[Model]) -> frozenset[str]:
    """The fields of ``model`` ``user`` may write: what they read, less what they may not edit."""
    return _allowed(user, model, FIELD_ACTIONS)


def field_names(model: type[Model]) -> tuple[str, ...]:
    """The fields of ``model`` itself - not the relations other models have to it."""
    meta = model._meta
    return tuple(field.name for field in (*meta.fields, *meta.many_to_many))


def path_readable(user: User, model: type[Model], path: str) -> bool:
    """
    Whether a lookup - ``region``, ``applicant__region``, ``-amount`` - reads
    only fields ``user`` may read. Searching, filtering or ordering by a field
    tells somebody what it holds as surely as showing it.
    """
    current = model

    for name in path.lstrip('-^=@$').split('__'):
        try:
            field = current._meta.get_field(name)
        except FieldDoesNotExist:
            return True  # a lookup such as icontains: nothing further is read

        if protection_of(user).protects(current, name) and name not in readable_fields(
            user, current
        ):
            return False

        if field.related_model is None:
            return True

        current = field.related_model

    return True


def field_permissions(model: type[Model], name: str) -> dict[str, str]:
    """``{'view': ..., 'edit': ...}`` - the two permissions of ``model.name``."""
    return {action: field_permission(model, name, action) for action in FIELD_ACTIONS}


def protection_problem(model: type[Model], name: str) -> str | None:
    """
    Why ``model.name`` cannot be protected, or ``None`` when it can.

    The primary key is how a row is found, and the password is never shown
    to anybody; neither can be hidden from somebody who reads the row.
    """
    try:
        field = model._meta.get_field(name)
    except FieldDoesNotExist:
        return f'{model.__name__} has no field {name!r}.'

    if name not in field_names(model):
        return f'{model.__name__}.{name} is a relation of another model, not a field of its own.'

    if getattr(field, 'primary_key', False):
        return f'{model.__name__}.{name} is the primary key, how a row is found.'

    if issubclass(model, AbstractBaseUser) and name == 'password':
        return f'{model.__name__}.{name} is the password, which is never shown at all.'

    return None


def _allowed(user: User, model: type[Model], actions: Iterable[str]) -> frozenset[str]:
    names = field_names(model)

    if getattr(user, 'is_superuser', False) and user.is_active:
        return frozenset(names)

    protected = protection_of(user).fields(model)

    if not protected:
        return frozenset(names)

    held = grants_of(user)
    return frozenset(
        name
        for name in names
        if name not in protected
        or all(held.holds(field_permission(model, name, action)) for action in actions)
    )


def model_key(model: type[Model]) -> ModelKey:
    """How the library's tables name a model: ``(app_label, model_name)`` of its concrete model."""
    meta = model._meta.concrete_model._meta  # type: ignore[union-attr]
    return meta.app_label, str(meta.model_name)
