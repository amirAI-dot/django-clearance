"""
Actions beyond view, create, edit and delete - the two kinds there are.

**A status action writes values.** Approving an order sets its status to
*approved* or *rejected*; nothing else does. Declared in code
(``build_permissions(status_actions=...)``) or made in the database
(``AccessService.create_status_action``), it **claims** its values: only
somebody allowed the action - its permission, the row within its scope, and
the row's current value among its ``from`` - writes them. A value no action
claims is written by whoever may write the row; several actions may claim
one field::

    writable_values(user, Order, 'status', order)   # {'pending', 'cancelled'}

The other kind - an action that does something new, found in the code - is
``clearance.discovery``'s.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models
from django.db.models import Model

from clearance.fields import ModelKey, model_key, writable_fields
from clearance.grants import KEPT_PREFIX
from clearance.models import StatusAction
from clearance.permissions import (
    DEFAULT_ACTIONS,
    declared_status_actions,
    is_action_name,
)
from clearance.protocols import User
from clearance.registry import registry

#: The actions every model has: never a status action, never found.
STANDARD_ACTIONS: Final = frozenset({*DEFAULT_ACTIONS, 'list'})

#: Where the status actions are kept on a user object once read.
_CACHE_ATTRIBUTE = f'{KEPT_PREFIX}status_actions'


# ---------------------------------------------------------------------- status actions


@dataclass(frozen=True)
class Transition:
    """One status action: the values of one field it claims, and where from."""

    model: type[Model]
    code: str
    field: str
    to: frozenset[Any]
    start: frozenset[Any]

    def starts_from(self, current: object) -> bool:
        """Whether it may write from ``current``: from anywhere when ``from`` is empty."""
        return not self.start or current in self.start


def values_of(model: type[Model], field: str) -> frozenset[Any] | None:
    """Every value ``model.field`` can hold - its choices, or yes and no - or ``None``."""
    found = model._meta.get_field(field)

    if isinstance(found, models.BooleanField):
        return frozenset({True, False})

    if getattr(found, 'choices', None):
        return frozenset(value for value, _ in found.flatchoices)  # type: ignore[union-attr]

    return None


def status_action_problems(
    model: type[Model], code: str, field: str, to: Sequence[object], start: Sequence[object]
) -> list[str]:
    """What is wrong with a status action, said in full - for a refusal and for E015."""
    problems = []

    if not is_action_name(code):
        problems.append(f'{code!r} is not an action: use lowercase words joined by underscores.')
    elif code in STANDARD_ACTIONS:
        problems.append(f'{code!r} is an action every model has already.')

    try:
        every = values_of(model, field)
    except FieldDoesNotExist:
        return [*problems, f'{model.__name__} has no field {field!r}.']

    if every is None:
        return [*problems, f'{model.__name__}.{field} has no choices, and is not yes or no.']

    if not to:
        problems.append('It writes no value.')

    for value in (*to, *start):
        if _clean(model, field, value) not in every:
            problems.append(f'{value!r} is not one of the values of {model.__name__}.{field}.')

    return problems


def transition(
    model: type[Model], code: str, field: str, to: Iterable[object], start: Iterable[object]
) -> Transition:
    """A status action, its values in the field's own types."""
    return Transition(
        model,
        code,
        field,
        frozenset(_clean(model, field, value) for value in to),
        frozenset(_clean(model, field, value) for value in start),
    )


class StatusActions:
    """Every status action as it stands: declared in code, or made in the database."""

    def __init__(self, stored: Mapping[ModelKey, tuple[Transition, ...]]) -> None:
        self._stored = MappingProxyType(dict(stored))

    @classmethod
    def load(cls) -> 'StatusActions':
        """What the database holds, read in one query."""
        stored: dict[ModelKey, list[Transition]] = {}

        for row in StatusAction.objects.select_related('content_type'):
            model = row.content_type.model_class()

            if model is None or _missing(model, row.field):
                continue  # nothing left to write - clearance_check lists it

            found = transition(model, row.code, row.field, row.to_values, row.from_values)
            stored.setdefault(model_key(model), []).append(found)

        return cls({key: tuple(found) for key, found in stored.items()})

    def of(self, model: type[Model]) -> tuple[Transition, ...]:
        declared = tuple(
            transition(model, code, spec['field'], spec['to'], spec['from'])
            for code, spec in declared_status_actions(model).items()
            if not _missing(model, spec['field'])
        )
        return (*declared, *self._stored.get(model_key(model), ()))

    def on(self, model: type[Model], field: str) -> tuple[Transition, ...]:
        return tuple(found for found in self.of(model) if found.field == field)

    def fields(self, model: type[Model]) -> frozenset[str]:
        """The fields of ``model`` some status action writes."""
        return frozenset(found.field for found in self.of(model))


def status_actions_of(user: object) -> StatusActions:
    """The status actions, read once for ``user``'s request and kept on them."""
    cached: StatusActions | None = getattr(user, _CACHE_ATTRIBUTE, None)

    if cached is None:
        cached = StatusActions.load()
        setattr(user, _CACHE_ATTRIBUTE, cached)

    return cached


def writable_values(
    user: User, model: type[Model], field: str, obj: Model | None = None
) -> frozenset[Any]:
    """
    The values of ``field`` ``user`` may write to ``obj`` - or to a new row.

    Nothing when they may not write the field; every value for the superuser.
    Otherwise every value no status action claims, the value the row holds
    already - keeping it is no change - and the values of every action
    claiming them that they are allowed, from where the row stands.
    """
    every = values_of(model, field)

    if every is None:
        raise ValueError(f'{model.__name__}.{field} has no values to choose from.')

    if field not in writable_fields(user, model):
        return frozenset()

    transitions = status_actions_of(user).on(model, field)

    if not transitions or (getattr(user, 'is_superuser', False) and user.is_active):
        return every

    saved = obj if obj is not None and obj.pk is not None else None
    current = getattr(saved, field) if saved is not None else _default(model, field)
    policy = registry.policy_for(model)
    claimed = frozenset().union(*(found.to for found in transitions))
    allowed = {
        code
        for code in dict.fromkeys(found.code for found in transitions)
        if policy.allows(user, code, saved)
    }
    given = frozenset().union(
        *(found.to for found in transitions if found.code in allowed and found.starts_from(current))
    )

    return (every - claimed) | given | (every & {current})


def _clean(model: type[Model], field: str, value: object) -> object:
    """``value`` as the field holds it - ``'1'`` is ``1`` for a number - or as it was."""
    try:
        return model._meta.get_field(field).to_python(value)  # type: ignore[union-attr]
    except ValidationError:
        return value


def _default(model: type[Model], field: str) -> object:
    return model._meta.get_field(field).get_default()  # type: ignore[union-attr]


def _missing(model: type[Model], field: str) -> bool:
    try:
        return values_of(model, field) is None
    except FieldDoesNotExist:
        return True
