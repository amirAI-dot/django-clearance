"""
Which rows a person may reach: the queryset's answer, and nobody else's.

DRF calls ``has_object_permission`` only once a view has resolved one object,
and Django's generic views have no such hook at all. So a list protected by
a permission check returns every row in the table - and nothing fails, which
is what makes it dangerous. The rows are therefore the queryset's to decide::

    Order.objects.visible_to(user, 'edit')        # a model with a ScopedQuerySet
    visible(Order.objects.all(), user, 'edit')    # any model at all

A person reaches the union of the scopes of every grant of the action's
permission that reaches them - each bundle's, and their own. A scope is one
of three things:

* ``all`` - every row, always offered;
* a **code scope** - a ``scope_<code>`` method a ``ScopedQuerySet`` lists in
  ``scopes``, for a rule too intricate to build;
* a **rule scope** - built by an administrator from conditions
  (``clearance.rules``), for any model, scoped in code or not.

A grant with no scope reaches the queryset's ``default_scope``. A
``ScopedQuerySet`` names none unless its developer chose one, so such a grant
reaches no rows; a model with a plain manager defaults to every row, as
Django always has, until a scope is chosen.

A code scope answers with one of:

* ``Q(...)`` - these rows, the cheapest to combine;
* ``Q()`` - every row;
* a queryset of the same model - these rows;
* ``None`` or ``self.none()`` - nothing.
"""

import logging
from collections.abc import Mapping
from functools import reduce
from operator import or_
from types import MappingProxyType
from typing import Any, ClassVar, Self, TypeAlias, TypeVar

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.query import EmptyQuerySet
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from clearance.fields import protection_of
from clearance.grants import KEPT_PREFIX, grants_of
from clearance.models import ScopeRule
from clearance.permissions import permission_for
from clearance.protocols import User
from clearance.rules import Rule

logger = logging.getLogger('clearance')

ModelT = TypeVar('ModelT', bound=models.Model)
QuerySetT = TypeVar('QuerySetT', bound=models.QuerySet[Any])

#: What a scope may answer.
Rows: TypeAlias = Q | models.QuerySet[Any] | None

#: The scope every model offers: every row.
EVERY_ROW = 'all'

#: Where a person's rule scopes are kept on their user object, per model, once read.
_RULES_ATTRIBUTE = f'{KEPT_PREFIX}rules'


class ScopedQuerySet(models.QuerySet[ModelT]):
    """A queryset that knows which of its rows each person may reach, with scopes in code."""

    #: The scopes this model offers in code, each with the label an administrator reads.
    scopes: ClassVar[Mapping[str, str | Promise]] = MappingProxyType({})

    #: What a grant with no scope chosen reaches. ``None`` - no rows - unless named.
    default_scope: ClassVar[str | None] = None

    #: What a scope method's name starts with: the scope ``own`` is ``scope_own``.
    hook_prefix: ClassVar[str] = 'scope_'

    @classmethod
    def offered_scopes(cls) -> dict[str, str | Promise]:
        """``all`` and the scopes in code. ``offered_scopes(model)`` adds the rule scopes."""
        return {EVERY_ROW: _('Every row'), **cls.scopes}

    def visible_to(self, user: User, action: str = 'view') -> Self:
        """
        The rows ``user`` may reach for ``action``.

        A queryset that answers in a way of its own overrides this - and is
        asked by ``visible`` too, so a view, the admin site and a policy get
        the answer the queryset gives.
        """
        return rows_reached(self, user, action)

    def code_scope(self, code: str, user: User) -> Rows:
        rows: Rows = getattr(self, f'{self.hook_prefix}{code}')(user)
        return rows


class OwnedQuerySet(ScopedQuerySet[ModelT]):
    """
    Rows that each belong to one account, offering ``own``.

    ``owner_path`` is the lookup from a row to the account that owns it. A
    subclass adds scopes of its own beside ``own``:
    ``scopes = {**OwnedQuerySet.scopes, 'branch': ...}``.
    """

    owner_path: ClassVar[str] = 'user'
    scopes: ClassVar[Mapping[str, str | Promise]] = MappingProxyType({'own': _('Their own')})

    def scope_own(self, user: User) -> Q:
        return Q(**{self.owner_path: user})


class SignedInReadQuerySet(ScopedQuerySet[ModelT]):
    """
    Every row, for anybody signed in, whatever they hold.

    For reference data - branches, kinds of loan - that describes how the
    platform works rather than anything about a person. Who may change it is
    still the policy's to say.
    """

    def visible_to(self, user: User, action: str = 'view') -> Self:
        if user.is_authenticated and user.is_active:
            return self.all()
        return self.none()


# ---------------------------------------------------------------------- any queryset


def visible(queryset: QuerySetT, user: User, action: str = 'view') -> QuerySetT:
    """
    The rows of ``queryset`` ``user`` may reach for ``action`` - for any model.

    Signed out or switched off, no rows; the superuser, every row; otherwise
    the union of the scopes of the action's grants. A ``ScopedQuerySet`` is
    asked through its ``visible_to``, so one that answers in a way of its own
    - ``SignedInReadQuerySet``, or a project's - answers here as well.
    """
    if isinstance(queryset, ScopedQuerySet):
        return queryset.visible_to(user, action)

    return rows_reached(queryset, user, action)


def answers_for_itself(queryset: models.QuerySet[Any]) -> bool:
    """Whether ``queryset`` overrides ``visible_to``: its grants then do not say what it reaches."""
    return (
        isinstance(queryset, ScopedQuerySet)
        and type(queryset).visible_to is not ScopedQuerySet.visible_to
    )


def rows_reached(queryset: QuerySetT, user: User, action: str = 'view') -> QuerySetT:
    """The rows the grants of ``action`` reach: what ``visible_to`` answers unless overridden."""
    if not (user.is_authenticated and user.is_active):
        return queryset.none()

    if getattr(user, 'is_superuser', False):
        return queryset.all()

    names = scopes_reaching(queryset, user, action)

    if names is None:
        return queryset.none()

    return _combine(queryset, [rows_in(queryset, name, user) for name in sorted(names)])


def scopes_reaching(queryset: models.QuerySet[Any], user: User, action: str) -> set[str] | None:
    """
    The scopes ``user`` holds the action in on this model - with the default
    put in for a grant with none - or ``None`` when they do not hold it.
    """
    given = grants_of(user).scopes(permission_for(queryset.model, action))

    if given is None:
        return None

    default = queryset.default_scope if isinstance(queryset, ScopedQuerySet) else EVERY_ROW
    return {default if scope is None else scope for scope in given} - {None}  # type: ignore[return-value]


def rows_in(queryset: models.QuerySet[Any], scope: str, user: User) -> Rows:
    """
    The rows ``scope`` gives ``user``.

    A scope the model no longer offers - removed from the code, or a rule
    whose fields are gone - reaches nothing, rather than everything.
    """
    if scope == EVERY_ROW:
        return Q()

    if isinstance(queryset, ScopedQuerySet) and scope in queryset.scopes:
        return queryset.code_scope(scope, user)

    rule = rule_scopes(user, queryset.model).get(scope)
    return rule.q(user) if rule is not None else None


def code_scopes(model: type[models.Model]) -> dict[str, str | Promise]:
    """``all`` and the scopes ``model`` offers in code - read with no query."""
    rows = model._default_manager.all()
    return (
        rows.offered_scopes() if isinstance(rows, ScopedQuerySet) else {EVERY_ROW: _('Every row')}
    )


def offered_scopes(model: type[models.Model]) -> dict[str, str | Promise]:
    """Every scope an administrator may choose for ``model``: ``all``, code, rules."""
    offered = code_scopes(model)
    content_type = ContentType.objects.get_for_model(model)

    for code, name in ScopeRule.objects.filter(content_type=content_type).values_list(
        'code', 'name'
    ):
        offered.setdefault(code, name)

    return offered


def rule_scopes(user: User, model: type[models.Model]) -> dict[str, Rule]:
    """
    The rule scopes of ``model``, checked - read once per request, kept on the user.

    A rule that no longer checks out against its model - a field gone, or
    protected since - is left out and logged: it reaches nothing until
    somebody fixes it, and ``clearance_check`` lists it.
    """
    kept: dict[type[models.Model], dict[str, Rule]] = getattr(user, _RULES_ATTRIBUTE, None) or {}

    if model not in kept:
        content_type = ContentType.objects.get_for_model(model)
        stored_rules = ScopeRule.objects.filter(content_type=content_type).read()
        protection = protection_of(user) if stored_rules else None
        found: dict[str, Rule] = {}

        for code, match, conditions in stored_rules:
            try:
                found[code] = Rule.parse(model, match, conditions, protection=protection)
            except ValidationError as error:
                logger.warning(
                    'Scope rule %r of %s reaches nothing until it is fixed: %s',
                    code,
                    model._meta.label,
                    '; '.join(error.messages),
                )

        kept[model] = found
        setattr(user, _RULES_ATTRIBUTE, kept)

    return kept[model]


def _combine(queryset: QuerySetT, scopes: list[Rows]) -> QuerySetT:
    """
    The union of ``scopes``.

    They are joined with OR in a single ``filter`` of the queryset asked
    about, a queryset a scope answered with joining as ``pk__in`` it - which
    never meets the limits of combining querysets with ``|``, and keeps
    whatever the queryset was narrowed by already: a scope says which rows,
    never that the rows asked about are other ones.
    """
    reached: list[Q | models.QuerySet[Any]] = []
    name = type(queryset).__name__

    for scope in scopes:
        if scope is None or isinstance(scope, EmptyQuerySet):
            continue

        if isinstance(scope, Q):
            if not scope:
                return queryset.all()
            reached.append(scope)
        elif isinstance(scope, models.QuerySet):
            if scope.model is not queryset.model:
                raise TypeError(
                    f'A scope of {name} answered with rows of {scope.model.__name__}, '
                    f'not {queryset.model.__name__}.'
                )
            reached.append(scope)
        else:
            raise TypeError(
                f'A scope of {name} answered with {type(scope).__name__}. '
                f'Answer with Q, a queryset, or None.'
            )

    if not reached:
        return queryset.none()

    conditions = [
        scope if isinstance(scope, Q) else Q(pk__in=scope.values('pk')) for scope in reached
    ]
    return queryset.filter(reduce(or_, conditions))
