"""
Django's own views, scoped and asking the policy.

Three mixins, for templates and forms as much as for an API:

``ScopedQuerySetMixin`` narrows the view's queryset to the rows the person
reaches for the view's action, in ``get_queryset`` - so a list shows only
those, and a page for anybody else's row is a 404, exactly as if it did not
exist. It works with Django's generic views and DRF's alike, and with any
model: one with no scopes in code is scoped by the rules an administrator
builds for it.

``PolicyRequiredMixin`` asks the policy, the way DRF's bridge does: first
with no object, in ``dispatch``, before anything runs; then, for a view with
an object, with the object, once ``get_object`` has found it among the rows
the person reaches::

    class OrderApproveView(PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):
        policy_action = 'approve'
        queryset = Order.objects.all()

The action is ``policy_action`` when named, and otherwise read off the view -
``list`` for a ``ListView``, ``edit`` for an ``UpdateView``, DRF's own
action on a viewset. The policy is ``policy`` when named, and otherwise the
model's own. A view neither can be read off is refused as misconfigured,
never let through.

``ProtectedFieldsViewMixin`` builds the view's form with
``ProtectedFieldsFormMixin`` - leaving out the protected fields the person may
not read, and disabling those they may not write - and tells the template
which fields those are, as ``readable_fields`` and ``writable_fields``::

    {% if 'rate' in readable_fields %}{{ object.rate }}{% endif %}
"""

from collections.abc import Callable, Iterable, Iterator, Mapping
from types import MappingProxyType
from typing import Any, Final, cast

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Model, QuerySet
from django.http import HttpRequest, HttpResponseBase
from django.urls import URLPattern, URLResolver, get_resolver
from django.views.generic.detail import BaseDetailView
from django.views.generic.edit import BaseCreateView, BaseDeleteView, BaseUpdateView
from django.views.generic.list import BaseListView

from clearance.fields import readable_fields, writable_fields
from clearance.forms import ProtectedFieldsFormMixin
from clearance.policies import BasePolicy
from clearance.protocols import user_of
from clearance.querysets import visible
from clearance.registry import registry

#: How an action is read off a Django generic view, most specific first:
#: a ``DeleteView`` is a ``BaseDetailView`` too.
GENERIC_VIEW_ACTIONS: Final[tuple[tuple[type, str], ...]] = (
    (BaseCreateView, 'create'),
    (BaseUpdateView, 'edit'),
    (BaseDeleteView, 'delete'),
    (BaseDetailView, 'view'),
    (BaseListView, 'list'),
)

#: DRF's viewset actions, in the library's words. Any other is a custom action.
DRF_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        'list': 'list',
        'retrieve': 'view',
        'create': 'create',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
        'metadata': 'list',
    }
)


def action_of(view: object) -> str | None:
    """
    The action a view performs: ``policy_action`` when it names one, DRF's
    action on a viewset, or the one a generic view's class implies.
    """
    named: str | None = getattr(view, 'policy_action', None)

    if named is not None:
        return named

    drf_action = getattr(view, 'action', None)

    if isinstance(drf_action, str):
        return DRF_ACTIONS.get(drf_action, drf_action)

    view_class = view if isinstance(view, type) else type(view)

    for generic, action in GENERIC_VIEW_ACTIONS:
        if issubclass(view_class, generic):
            return action

    return None


def model_of(view: object) -> type[Model] | None:
    """The model a view declares, through ``model`` or ``queryset``, without running it."""
    model = getattr(view, 'model', None)

    if model is None:
        queryset = getattr(view, 'queryset', None)
        model = getattr(queryset, 'model', None)

    return model if isinstance(model, type) and issubclass(model, Model) else None


def urlconf_callbacks(
    patterns: Iterable[URLPattern | URLResolver] | None = None,
) -> Iterator[Callable[..., Any]]:
    """Every view the URLconf routes to, through every ``include``."""
    for pattern in get_resolver().url_patterns if patterns is None else patterns:
        if isinstance(pattern, URLResolver):
            yield from urlconf_callbacks(pattern.url_patterns)
        else:
            yield pattern.callback


class ScopedQuerySetMixin:
    """Narrows the view's queryset to the rows the person reaches for its action."""

    request: HttpRequest

    #: The action whose scope narrows the rows. Read off the view when left out.
    scope_action: str | None = None

    def get_scope_action(self) -> str:
        return self.scope_action or action_of(self) or 'view'

    def get_queryset(self) -> QuerySet[Any]:
        queryset: QuerySet[Any] = cast(Any, super()).get_queryset()
        return visible(queryset, user_of(self.request), self.get_scope_action())


class PolicyRequiredMixin(AccessMixin):
    """Asks the policy whether the person may do the view's action."""

    request: HttpRequest

    #: The policy to ask. The model's own when left out.
    policy: BasePolicy | None = None

    #: The action to ask about. Read off the view when left out.
    policy_action: str | None = None

    @classmethod
    def resolved_action(cls) -> str | None:
        """``policy_action``, or the one read off the view, or ``None``."""
        return action_of(cls)

    @classmethod
    def resolved_policy(cls) -> BasePolicy | None:
        """``policy``, or the policy of the view's model, or ``None``."""
        if cls.policy is not None:
            return cls.policy

        model = model_of(cls)
        return registry.policy_for(model) if model is not None else None

    @classmethod
    def configuration_errors(cls) -> list[str]:
        """What stops this view from asking a policy - for the system check too."""
        errors = []
        policy = cls.resolved_policy()
        action = cls.resolved_action()

        if policy is None:
            errors.append(
                f'{cls.__name__} uses PolicyRequiredMixin but names no policy, '
                f'and has no model whose policy could be asked.'
            )

        if action is None:
            errors.append(
                f'{cls.__name__} names no policy_action, and none can be read off it: it is '
                f'not a ListView, DetailView, CreateView, UpdateView or DeleteView.'
            )
        elif policy is not None:
            try:
                policy.hook(action)
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
        policy = cast(BasePolicy, self.resolved_policy())
        action = cast(str, self.resolved_action())
        return policy.allows(user_of(self.request), action, obj)


class ProtectedFieldsViewMixin:
    """Builds the view's form for the person, and tells its template which fields they may see."""

    request: HttpRequest

    def get_form_class(self) -> type[Any]:
        form_class: type[Any] = cast(Any, super()).get_form_class()

        if issubclass(form_class, ProtectedFieldsFormMixin):
            return form_class

        # Built by the form's own metaclass, as Django builds a ModelForm.
        metaclass: Any = type(form_class)
        protected: type[Any] = metaclass(
            form_class.__name__,
            (ProtectedFieldsFormMixin, form_class),
            {'__module__': form_class.__module__},
        )
        return protected

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = cast(Any, super()).get_form_kwargs()
        return {**kwargs, 'user': user_of(self.request)}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = cast(Any, super()).get_context_data(**kwargs)
        found = getattr(self, 'object', None)
        model = model_of(self) or (type(found) if isinstance(found, Model) else None)

        if model is not None:
            user = user_of(self.request)
            context.setdefault('readable_fields', readable_fields(user, model))
            context.setdefault('writable_fields', writable_fields(user, model))

        return context
