"""
DRF asking the policy: ``ModelPolicyPermission`` for a view of a model,
``PolicyPermission`` for a view naming the policy it asks::

    class OrderViewSet(ScopedQuerySetMixin, viewsets.ModelViewSet):
        permission_classes = [ModelPolicyPermission]

    class OrderReport(APIView):
        permission_classes = [PolicyPermission]
        policy = order_access.policy
        policy_action = 'report'

The action is the viewset's, in the library's words - ``list``, ``view`` for
``retrieve``, ``create``, ``edit`` for ``update``, ``delete``, or an
``@action``'s own name - ``policy_action`` when the view names one, and an
``APIView``'s HTTP method otherwise. The policy is asked without the object
first, and again with it once DRF has found it.

**On every serializer, a write is guarded.** A value the person may not write
- a protected field, a value a status action claims - is refused with a 400
naming the field, before the serializer runs: a serializer that never heard
of this library cannot write what it should not.

DRF imports this module while it is still importing its own views - when
``DEFAULT_PERMISSION_CLASSES`` names a class here - so nothing here imports
``rest_framework.views`` or ``rest_framework.generics`` before it is asked.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission

from clearance.policies import BasePolicy
from clearance.protocols import user_of
from clearance.registry import registry
from clearance.views import ScopedQuerySetMixin, action_of, model_of
from clearance.writes import refused_writes

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

#: An ``APIView``'s action, read off its HTTP method when it names none.
METHOD_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        'GET': 'view',
        'HEAD': 'view',
        'OPTIONS': 'view',
        'POST': 'create',
        'PUT': 'edit',
        'PATCH': 'edit',
        'DELETE': 'delete',
    }
)


def api_action(request: Request, view: APIView) -> str | None:
    """The action ``view`` performs for ``request``, or ``None`` for a method nobody maps."""
    return action_of(view) or METHOD_ACTIONS.get(str(request.method))


class PolicyPermission(BasePermission):
    """Asks the policy the view names in ``policy``."""

    @classmethod
    def policy_for_view(cls, view: type[APIView] | APIView) -> BasePolicy | None:
        """The policy asked for ``view``, read off its class - ``None`` when it names none."""
        policy = getattr(view, 'policy', None)
        return policy if isinstance(policy, BasePolicy) else None

    def policy_of(self, view: APIView) -> BasePolicy:
        policy = self.policy_for_view(view)

        if policy is None:
            raise ImproperlyConfigured(
                f'{type(view).__name__} is guarded by {type(self).__name__}, but there is no '
                f'policy to ask.'
            )

        return policy

    def has_permission(self, request: Request, view: APIView) -> bool:
        policy, action = self.policy_of(view), api_action(request, view)

        if action is None or not policy.allows(user_of(request), action):
            return False

        if action == 'create':
            self.refuse_writes(request, policy, None)

        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        policy, action = self.policy_of(view), api_action(request, view)

        if action is None or not policy.allows(user_of(request), action, obj):
            return False

        if action == 'edit':
            self.refuse_writes(request, policy, obj)

        return True

    @staticmethod
    def refuse_writes(request: Request, policy: BasePolicy, obj: Model | None) -> None:
        """A 400 naming every field the request sends that the person may not write."""
        if policy.model is None:
            return

        for item in _items(request.data):
            refused = refused_writes(user_of(request), policy.model, item, obj)

            if refused:
                raise ValidationError({name: [why] for name, why in refused.items()})


class ModelPolicyPermission(PolicyPermission):
    """Asks the policy of the view's model - from ``queryset``, or ``get_queryset()``."""

    @classmethod
    def policy_for_view(cls, view: type[APIView] | APIView) -> BasePolicy | None:
        model = model_of(view)
        return registry.policy_for(model) if model is not None else None

    def policy_of(self, view: APIView) -> BasePolicy:
        policy = self.policy_for_view(view)

        if policy is not None:
            return policy

        queryset = view.get_queryset() if finds_model_by_queryset(type(view)) else None  # type: ignore[attr-defined]
        model = getattr(queryset, 'model', None)

        if model is None:
            raise ImproperlyConfigured(
                f'{type(view).__name__} is guarded by ModelPolicyPermission, but has no '
                f'queryset to find its model by.'
            )

        return registry.policy_for(model)


def finds_model_by_queryset(view: type[APIView]) -> bool:
    """
    Whether ``view`` has a ``get_queryset`` of its own to find its model by -
    one written for it, not DRF's or the scoping mixin's, which only read
    ``queryset``.
    """
    definer = next((klass for klass in view.__mro__ if 'get_queryset' in vars(klass)), None)
    from rest_framework.generics import GenericAPIView

    return definer not in (None, GenericAPIView, ScopedQuerySetMixin)


def _items(data: object) -> Iterator[Mapping[str, Any]]:
    """The values sent: one object, or each of a list of them."""
    if isinstance(data, Mapping):
        yield data
    elif isinstance(data, list):
        yield from (item for item in data if isinstance(item, Mapping))
