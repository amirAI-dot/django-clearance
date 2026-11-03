"""
Which rows a person may reach: the queryset's answer, and nobody else's.

DRF calls ``has_object_permission`` only once a view has resolved one object,
and Django's generic views have no such hook at all. So a list protected by
a permission check returns every row in the table - and nothing fails, which
is what makes it dangerous. The rows are therefore the queryset's to decide::

    class LoanQuerySet(ScopedQuerySet):
        def scope_for_customer(self, user):
            return Q(applicant=user)

        def scope_for_officer(self, user):
            return Q(branch__officers=user)

    Loan.objects.visible_to(user)

``visible_to`` asks one hook per role the person has, and the rows are the
**union** of what the hooks answer. A role with no hook sees nothing - unless
it is in ``CLEARANCE['EVERY_ROW_ROLES']`` - so a forgotten hook is an empty
list, never a leak.

A hook answers with one of:

* ``Q(...)`` - these rows, the cheapest to combine;
* ``Q()`` - every row;
* a queryset of the same model - these rows;
* ``None`` or ``self.none()`` - nothing.
"""

from functools import reduce
from operator import or_
from typing import Any, ClassVar, Self, TypeAlias, TypeVar

from django.db import models
from django.db.models import Q
from django.db.models.query import EmptyQuerySet

from clearance.conf import clearance_settings
from clearance.protocols import User
from clearance.resolvers import roles_of

ModelT = TypeVar('ModelT', bound=models.Model)

#: What a scope hook may answer.
Scope: TypeAlias = Q | models.QuerySet[Any] | None


class ScopedQuerySet(models.QuerySet[ModelT]):
    """A queryset that knows which of its rows each person may reach."""

    #: What a hook's name starts with: the role ``officer`` is ``scope_for_officer``.
    scope_prefix: ClassVar[str] = 'scope_for_'

    def visible_to(self, user: User) -> Self:
        """The rows ``user`` may reach."""
        if not (user.is_authenticated and user.is_active):
            return self.none()

        if getattr(user, 'is_superuser', False):
            return self.all()

        scopes = [self.scope_for(role, user) for role in sorted(roles_of(user))]
        return self._combine(scopes)

    def scope_for(self, role: str, user: User) -> Scope:
        """The rows ``role`` gives ``user``: its hook's answer, or the default."""
        hook = getattr(self, f'{self.scope_prefix}{role}', None)

        if hook is None:
            return self.default_scope(role, user)

        scope: Scope = hook(user)
        return scope

    def default_scope(self, role: str, user: User) -> Scope:
        """
        The rows for a role with no hook here: every row for a role in
        ``EVERY_ROW_ROLES``, otherwise none.

        Override it to change what an unwritten hook means for every role at
        once - ``OwnedQuerySet`` makes it "the rows that are yours".
        """
        if role in clearance_settings.every_row_roles:
            return Q()
        return None

    def _combine(self, scopes: list[Scope]) -> Self:
        """
        The union of ``scopes``.

        One scope is applied as it is, so a queryset a hook built is returned
        unchanged. Several are joined with OR in a single ``filter``, a
        queryset joining as ``pk__in`` it - which never meets the limits of
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
                        f'A scope hook of {type(self).__name__} answered with rows of '
                        f'{scope.model.__name__}, not {self.model.__name__}.'
                    )
                reached.append(scope)
            else:
                raise TypeError(
                    f'A scope hook of {type(self).__name__} answered with '
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


class SignedInReadQuerySet(ScopedQuerySet[ModelT]):
    """
    Every row, for anybody signed in.

    For reference data - branches, kinds of loan - that describes how the
    platform works rather than anything about a person. Who may change it is
    still the policy's to say.
    """

    def visible_to(self, user: User) -> Self:
        if user.is_authenticated and user.is_active:
            return self.all()
        return self.none()


class OwnedQuerySet(ScopedQuerySet[ModelT]):
    """
    Rows that each belong to one account.

    A role with no hook of its own sees the rows it owns, found through
    ``owner_path``; a role in ``EVERY_ROW_ROLES`` still sees every row, and a
    hook still says otherwise for its role.
    """

    #: The lookup from a row to the account that owns it.
    owner_path: ClassVar[str] = 'user'

    def default_scope(self, role: str, user: User) -> Scope:
        if role in clearance_settings.every_row_roles:
            return Q()
        return Q(**{self.owner_path: user})
