"""
Which rows a person may reach: the queryset's answer, and nobody else's.

DRF calls ``has_object_permission`` only once a view has resolved one object,
and Django's generic views have no such hook at all. So a list protected by
a permission check returns every row in the table - and nothing fails, which
is what makes it dangerous. The rows are therefore the queryset's to decide::

    class OrderQuerySet(ScopedQuerySet):
        scopes = {
            'own': _('Their own orders'),
            'branch': _("Their branch's orders"),
        }

        def scope_own(self, user):
            return Q(customer__user=user)

        def scope_branch(self, user):
            return Q(branch__staff=user)

    Order.objects.visible_to(user, 'edit')

A person reaches the union of the scopes of every grant of the action's
permission that reaches them - each bundle's, and their own. ``all`` is
always offered and means every row. A grant with no scope reaches the
queryset's ``default_scope``; with none named, no rows.

A scope method answers with one of:

* ``Q(...)`` - these rows, the cheapest to combine;
* ``Q()`` - every row;
* a queryset of the same model - these rows;
* ``None`` or ``self.none()`` - nothing.
"""

from collections.abc import Mapping
from functools import reduce
from operator import or_
from types import MappingProxyType
from typing import Any, ClassVar, Self, TypeAlias, TypeVar

from django.db import models
from django.db.models import Q
from django.db.models.query import EmptyQuerySet
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from clearance.grants import grants_of
from clearance.permissions import permission_for
from clearance.protocols import User

ModelT = TypeVar('ModelT', bound=models.Model)

#: What a scope method may answer.
Rows: TypeAlias = Q | models.QuerySet[Any] | None

#: The scope every scoped model offers: every row.
EVERY_ROW = 'all'


class ScopedQuerySet(models.QuerySet[ModelT]):
    """A queryset that knows which of its rows each person may reach."""

    #: The scopes this model offers, each with the label an administrator reads.
    scopes: ClassVar[Mapping[str, str | Promise]] = MappingProxyType({})

    #: What a grant with no scope chosen reaches. ``None`` - no rows - unless named.
    default_scope: ClassVar[str | None] = None

    #: What a scope method's name starts with: the scope ``own`` is ``scope_own``.
    hook_prefix: ClassVar[str] = 'scope_'

    @classmethod
    def offered_scopes(cls) -> dict[str, str | Promise]:
        """Every scope an administrator may choose for this model, ``all`` first."""
        return {EVERY_ROW: _('Every row'), **cls.scopes}

    def visible_to(self, user: User, action: str = 'view') -> Self:
        """The rows ``user`` may reach for ``action``."""
        if not (user.is_authenticated and user.is_active):
            return self.none()

        if getattr(user, 'is_superuser', False):
            return self.all()

        given = grants_of(user).scopes(permission_for(self.model, action))

        if given is None:
            return self.none()

        names = {self.default_scope if scope is None else scope for scope in given}
        return self._combine([self.rows_in(name, user) for name in sorted(n for n in names if n)])

    def rows_in(self, scope: str, user: User) -> Rows:
        """
        The rows ``scope`` gives ``user``.

        A scope this queryset does not offer - one removed from the code since
        it was chosen - reaches nothing, rather than everything.
        """
        if scope == EVERY_ROW:
            return Q()

        if scope not in self.scopes:
            return None

        rows: Rows = getattr(self, f'{self.hook_prefix}{scope}')(user)
        return rows

    def _combine(self, scopes: list[Rows]) -> Self:
        """
        The union of ``scopes``.

        One scope is applied as it is, so a queryset a method built is
        returned unchanged. Several are joined with OR in a single ``filter``,
        a queryset joining as ``pk__in`` it - which never meets the limits of
        combining querysets with ``|``.
        """
        reached: list[Q | models.QuerySet[Any]] = []

        for scope in scopes:
            if scope is None or isinstance(scope, EmptyQuerySet):
                continue

            if isinstance(scope, Q):
                if not scope:
                    return self.all()
                reached.append(scope)
            elif isinstance(scope, models.QuerySet):
                if scope.model is not self.model:
                    raise TypeError(
                        f'A scope of {type(self).__name__} answered with rows of '
                        f'{scope.model.__name__}, not {self.model.__name__}.'
                    )
                reached.append(scope)
            else:
                raise TypeError(
                    f'A scope of {type(self).__name__} answered with '
                    f'{type(scope).__name__}. Answer with Q, a queryset, or None.'
                )

        if not reached:
            return self.none()

        if len(reached) == 1:
            (only,) = reached
            return only if isinstance(only, models.QuerySet) else self.filter(only)  # type: ignore[return-value]

        conditions = [
            scope if isinstance(scope, Q) else Q(pk__in=scope.values('pk')) for scope in reached
        ]
        return self.filter(reduce(or_, conditions))


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
