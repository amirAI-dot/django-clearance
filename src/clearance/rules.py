"""
Row scopes an administrator builds, from rules - no code.

A rule is conditions joined by *all of* or *any of*; a condition is a field,
an operator and a value::

    branch      is          the person's branch
    customer    is          the person
    price       at least    10000000

The value is a constant, or something of the person's: ``{'person': ''}`` is
the person, ``{'person': 'branch'}`` their branch - any field of the user,
reached the same way.

Two things make this safe to hand to an administrator. **A rule is only ever
a Django ``Q``** - never SQL, never code - built from fields that exist,
operators that suit them, and values of the right kind, all checked when the
rule is saved. And **no condition reads what its writer may not**: a filter
on a protected field would tell somebody without its view permission what it
holds - "the price is at least ten million" - and the password is never read
at all.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import reduce
from operator import and_, or_
from types import MappingProxyType
from typing import Any, Final, Self

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q, Subquery

from clearance.conf import clearance_settings
from clearance.protocols import User

#: Answers whether a field of a model may not be read by a rule. The
#: protected fields add theirs; the password is refused always.
unreadable_checks: list[Callable[[type[models.Model], str], bool]] = []

TEXT, NUMBER, DATE, BOOLEAN, RELATION, OTHER = (
    'text',
    'number',
    'date',
    'boolean',
    'relation',
    'other',
)
EVERY_KIND: Final = frozenset({TEXT, NUMBER, DATE, BOOLEAN, RELATION, OTHER})


def kind_of(field: Any) -> str:
    """What a field holds, as far as an operator cares."""
    if field.is_relation:
        return RELATION
    if isinstance(field, models.BooleanField):
        return BOOLEAN
    if isinstance(field, models.IntegerField | models.FloatField | models.DecimalField):
        return NUMBER
    if isinstance(field, models.DateField | models.TimeField | models.DurationField):
        return DATE
    if isinstance(field, models.CharField | models.TextField):
        return TEXT
    return OTHER


@dataclass(frozen=True)
class Operator:
    """How a field is compared with a value."""

    code: str
    lookup: str
    kinds: frozenset[str]
    #: ``one`` value, ``many``, or ``none``.
    takes: str = 'one'
    negated: bool = False


OPERATORS: Final[Mapping[str, Operator]] = MappingProxyType(
    {
        operator.code: operator
        for operator in (
            Operator('is', 'exact', EVERY_KIND),
            Operator('is_not', 'exact', EVERY_KIND, negated=True),
            Operator('is_one_of', 'in', EVERY_KIND - {BOOLEAN}, takes='many'),
            Operator('contains', 'icontains', frozenset({TEXT})),
            Operator('is_empty', 'isnull', EVERY_KIND, takes='none'),
            Operator('before', 'lt', frozenset({DATE})),
            Operator('after', 'gt', frozenset({DATE})),
            Operator('at_least', 'gte', frozenset({NUMBER, DATE})),
            Operator('at_most', 'lte', frozenset({NUMBER, DATE})),
        )
    }
)

MATCHES: Final = ('all', 'any')


@dataclass(frozen=True)
class Path:
    """A field of a model, reached through at most ``RULE_DEPTH`` relations."""

    model: type[models.Model]
    names: tuple[str, ...]
    field: Any

    @classmethod
    def resolve(cls, model: type[models.Model], path: str) -> Self:
        """The field ``path`` names on ``model``, or ``ValidationError`` saying why not."""
        names = tuple(path.split('__')) if path else ()
        depth = rule_depth()

        if len(names) - 1 > depth:
            raise ValidationError(f'{path!r} crosses more than {depth} relations.')

        current, field = model, None

        for position, name in enumerate(names):
            if field is not None:
                if not field.is_relation or field.related_model is None:
                    raise ValidationError(f'{path!r}: {names[position - 1]!r} leads nowhere.')
                current = field.related_model

            try:
                field = current._meta.get_field(name)
            except FieldDoesNotExist:
                raise ValidationError(
                    f'{path!r}: {current.__name__} has no field {name!r}.'
                ) from None

            if not readable(current, name):
                raise ValidationError(f'{path!r}: {current.__name__}.{name} may not be read.')

        return cls(model, names, field)

    @property
    def lookup(self) -> str:
        return '__'.join(self.names)

    @property
    def target(self) -> type[models.Model] | None:
        """The model a relation reaches - or, for an empty path, the model itself."""
        if self.field is None:
            return self.model
        return self.field.related_model if self.field.is_relation else None

    @property
    def kind(self) -> str:
        return RELATION if self.field is None else kind_of(self.field)


@dataclass(frozen=True)
class Condition:
    """One field, compared with one value."""

    field: Path
    operator: Operator
    constant: Any = None
    person: Path | None = None

    def q(self, user: User) -> Q:
        lookup, operator = self.field.lookup, self.operator

        if operator.takes == 'none':
            empty = Q(**{f'{lookup}__isnull': True})
            return empty | Q(**{lookup: ''}) if self.field.kind == TEXT else empty

        if self.person is not None:
            person: Any = getattr(user, 'pk', None)  # nobody signed in matches nothing
            values = get_user_model().objects.filter(pk=person).values(self.person.lookup or 'pk')
            if operator.code in ('is', 'is_not', 'is_one_of'):
                found = Q(**{f'{lookup}__in': values})
            else:
                found = Q(**{f'{lookup}__{operator.lookup}': Subquery(values[:1])})
        else:
            found = Q(**{f'{lookup}__{operator.lookup}': self.constant})

        return ~found if operator.negated else found


class Rule:
    """Conditions joined by *all of* or *any of*, checked once and turned into a ``Q``."""

    def __init__(self, model: type[models.Model], match: str, conditions: Sequence[Condition]):
        self.model = model
        self.match = match
        self.conditions = tuple(conditions)

    @classmethod
    def parse(cls, model: type[models.Model], match: str, raw: object) -> 'Rule':
        """
        The rule ``raw`` describes on ``model``, every condition checked, or a
        ``ValidationError`` naming each condition that is wrong, and how.
        """
        problems: list[str] = []

        if match not in MATCHES:
            problems.append(f'match must be one of {", ".join(MATCHES)}, not {match!r}.')

        if not isinstance(raw, list) or not raw:
            problems.append('A rule needs at least one condition; every row is the scope "all".')
            raise ValidationError(problems)

        conditions = []

        for number, item in enumerate(raw, start=1):
            try:
                conditions.append(parse_condition(model, item))
            except ValidationError as error:
                problems += [f'Condition {number}: {message}' for message in error.messages]

        if problems:
            raise ValidationError(problems)

        return cls(model, match, conditions)

    def q(self, user: User) -> Q:
        join = and_ if self.match == 'all' else or_
        return reduce(join, (condition.q(user) for condition in self.conditions))


def parse_condition(model: type[models.Model], item: object) -> Condition:
    if not isinstance(item, Mapping):
        raise ValidationError('A condition is a field, an operator and a value.')

    field = Path.resolve(model, str(item.get('field', '')))

    if field.field is None:
        raise ValidationError('A condition names a field.')

    operator = OPERATORS.get(str(item.get('operator')))

    if operator is None:
        raise ValidationError(
            f'{item.get("operator")!r} is not an operator. Choose one of {", ".join(OPERATORS)}.'
        )

    if field.kind not in operator.kinds:
        raise ValidationError(
            f'{operator.code!r} does not suit {field.lookup!r}, a {field.kind} field.'
        )

    value = item.get('value')

    if operator.takes == 'none':
        return Condition(field, operator)

    if not isinstance(value, Mapping) or len(value) != 1 or not {'constant', 'person'} & set(value):
        raise ValidationError('The value is {"constant": ...} or {"person": "<field>"}.')

    if 'person' in value:
        return Condition(field, operator, person=_person_path(field, str(value['person'])))

    return Condition(field, operator, constant=_constant(field, operator, value['constant']))


def _person_path(field: Path, path: str) -> Path:
    person = Path.resolve(get_user_model(), path)

    if field.kind == RELATION:
        if person.target is None or person.target is not field.target:
            raise ValidationError(
                f"{field.lookup!r} reaches {_name(field.target)}; the person's {path or 'self'!r} "
                f'is not one.'
            )
    elif person.kind != field.kind:
        raise ValidationError(
            f"{field.lookup!r} holds {field.kind}; the person's {path!r} holds {person.kind}."
        )

    return person


def _constant(field: Path, operator: Operator, value: object) -> object:
    if operator.takes == 'many':
        if not isinstance(value, list) or not value:
            raise ValidationError(f'{operator.code!r} takes a list of values.')
        return [_one_constant(field, item) for item in value]
    return _one_constant(field, value)


def _one_constant(field: Path, value: object) -> object:
    related = field.target if field.kind == RELATION else None
    target = related._meta.pk if related is not None else field.field

    try:
        cleaned = target.to_python(value)
    except ValidationError:
        raise ValidationError(f'{value!r} is not a value {field.lookup!r} can hold.') from None

    has_choices = related is None and getattr(field.field, 'choices', None)
    choices = {choice for choice, _ in field.field.flatchoices} if has_choices else None

    if choices is not None and cleaned not in choices:
        raise ValidationError(f'{value!r} is not one of the choices of {field.lookup!r}.')

    return cleaned


def readable(model: type[models.Model], name: str) -> bool:
    """Whether a rule may read ``model.name``: never a password, never a protected field."""
    if issubclass(model, AbstractBaseUser) and name == 'password':
        return False
    return not any(check(model, name) for check in unreadable_checks)


def rule_depth() -> int:
    return clearance_settings.rule_depth()


def _name(model: type[models.Model] | None) -> str:
    return model.__name__ if model is not None else 'nothing'
