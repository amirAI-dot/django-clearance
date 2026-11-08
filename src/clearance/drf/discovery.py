"""
The actions DRF's views ask for, found in the URLconf.

A view counts when one of its permission classes asks a policy
(``PolicyPermission`` or ``ModelPolicyPermission``). Each route a router made
for a viewset names its actions - ``{'post': 'print_invoice'}`` for an
``@action`` - and an ``APIView`` may name one in ``policy_action``.
"""

from collections.abc import Iterator

from rest_framework.views import APIView

from clearance.discovery import ActionFinder, FoundAction
from clearance.drf.permissions import PolicyPermission
from clearance.policies import BasePolicy
from clearance.views import DRF_ACTIONS, urlconf_callbacks


def guarding_policy(view: type[APIView]) -> BasePolicy | None:
    """The policy ``view``'s permission classes ask, read off the class - or ``None``."""
    for permission in view.permission_classes:
        if isinstance(permission, type) and issubclass(permission, PolicyPermission):
            return permission.policy_for_view(view)
    return None


def guarded_views() -> Iterator[tuple[type[APIView], dict[str, str]]]:
    """Every DRF view in the URLconf that asks a policy, with the actions its route maps."""
    for callback in urlconf_callbacks():
        view = getattr(callback, 'cls', None)

        if not (isinstance(view, type) and issubclass(view, APIView)):
            continue

        if any(
            isinstance(permission, type) and issubclass(permission, PolicyPermission)
            for permission in view.permission_classes
        ):
            yield view, dict(getattr(callback, 'actions', None) or {})


class APIViewFinder(ActionFinder):
    """DRF's views asking a policy: a viewset's ``@action``s, an ``APIView``'s ``policy_action``."""

    def find(self) -> Iterator[FoundAction]:
        for view, routed in guarded_views():
            policy = guarding_policy(view)

            if policy is None:
                continue  # it cannot ask anybody: E009 says so

            origin = f'{view.__module__}.{view.__qualname__}'
            named = getattr(view, 'policy_action', None)
            actions = [named] if named is not None else list(routed.values())

            for action in actions:
                yield FoundAction(policy, DRF_ACTIONS.get(action, action), origin)
