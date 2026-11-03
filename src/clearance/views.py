"""
Django's own views, scoped and asking the policy.

Two mixins, for templates and forms as much as for an API:

``ScopedQuerySetMixin`` narrows the view's queryset to the rows the person
may reach, in ``get_queryset`` - so a list shows only those, and a detail
page for anybody else's row is a 404, exactly as if it did not exist. It
works with Django's generic views and DRF's alike.

``PolicyRequiredMixin`` asks the policy, the way DRF's bridge does: first
with no object, in ``dispatch``, before anything runs; then, for a view with
an object, with the object, once ``get_object`` has found it among the rows
the person may reach::

    class LoanApproveView(PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):
        policy = loan_access.policy
        policy_action = 'approve'
        queryset = Loan.objects.all()

Without a ``policy_action``, the action is read off the view - ``list`` for a
``ListView``, ``edit`` for an ``UpdateView`` - and a view it cannot be read
off is refused as misconfigured, never let through.
"""

from typing import Any, ClassVar, cast

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Model, QuerySet
from django.http import HttpRequest, HttpResponseBase
from django.views.generic.detail import BaseDetailView
from django.views.generic.edit import BaseCreateView, BaseDeleteView, BaseUpdateView
from django.views.generic.list import BaseListView

from clearance.policies import BasePolicy
from clearance.protocols import user_of
from clearance.querysets import ScopedQuerySet


class ScopedQuerySetMixin:
    """Narrows the view's queryset to the rows the person may reach."""

    request: HttpRequest

    def get_queryset(self) -> QuerySet[Any]:
        queryset = cast(Any, super()).get_queryset()

        if not isinstance(queryset, ScopedQuerySet):
            raise ImproperlyConfigured(
                f'{type(self).__name__} uses ScopedQuerySetMixin, but its queryset is a '
                f'{type(queryset).__name__}. Give the model a ScopedQuerySet, or the view '
                f'shows every row to everybody.'
            )

        return queryset.visible_to(user_of(self.request))


class PolicyRequiredMixin(AccessMixin):
    """Asks ``policy`` whether the person may do ``policy_action``."""

    request: HttpRequest

    #: The policy to ask - usually ``loan_access.policy``.
    policy: BasePolicy | None = None

    #: The action to ask about. Read off the view when left out.
    policy_action: str | None = None

    #: How an action is read off a generic view, most specific first:
    #: a ``DeleteView`` is a ``BaseDetailView`` too.
    policy_actions: ClassVar[tuple[tuple[type, str], ...]] = (
        (BaseCreateView, 'create'),
        (BaseUpdateView, 'edit'),
        (BaseDeleteView, 'delete'),
        (BaseDetailView, 'view'),
        (BaseListView, 'list'),
    )

    @classmethod
    def resolved_action(cls) -> str | None:
        """``policy_action``, or the one read off the view, or ``None``."""
        if cls.policy_action is not None:
            return cls.policy_action

        for view_class, action in cls.policy_actions:
            if issubclass(cls, view_class):
                return action

        return None

    @classmethod
    def configuration_errors(cls) -> list[str]:
        """What stops this view from asking its policy - for the system check too."""
        errors = []

        if cls.policy is None:
            errors.append(f'{cls.__name__} uses PolicyRequiredMixin but names no policy.')

        if cls.resolved_action() is None:
            errors.append(
                f'{cls.__name__} names no policy_action, and none can be read off it: it is '
                f'not a ListView, DetailView, CreateView, UpdateView or DeleteView.'
            )
        elif cls.policy is not None:
            try:
                cls.policy.hook(cast(str, cls.resolved_action()))
            except ImproperlyConfigured as error:
                errors.append(f'{cls.__name__}: {error}')

        return errors

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        errors = self.configuration_errors()

        if errors:
            raise ImproperlyConfigured(' '.join(errors))

        if not self._allows(None):
            return self.handle_no_permission()

        response: HttpResponseBase = cast(Any, super()).dispatch(request, *args, **kwargs)
        return response

    def get_object(self, queryset: QuerySet[Any] | None = None) -> Model:
        obj: Model = cast(Any, super()).get_object(queryset)

        if not self._allows(obj):
            raise PermissionDenied

        return obj

    def _allows(self, obj: object | None) -> bool:
        policy = cast(BasePolicy, self.policy)
        action = cast(str, self.resolved_action())
        return policy.allows(user_of(self.request), action, obj)
