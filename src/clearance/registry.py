"""
The registry: one policy per resource, for the whole project.

Registering is what turns a policy class into something a view can use::

    loan_access = registry.register(LoanPolicy)

    loan_access.policy.allows(user, 'approve', loan)

The registry refuses a second policy for the same resource. Two policies
claiming one codename is almost always a copy and paste, and the second
would silently decide in the first one's place.

``policy_for(model)`` is how the library asks about a model: the policy
registered for it, or - for every model nobody wrote one for - a
``ModelPolicy`` made from its permissions, once.
"""

from collections.abc import Iterator
from typing import Any, Generic, TypeVar

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model

from clearance.policies import BasePolicy, ModelPolicy

PolicyT = TypeVar('PolicyT', bound=BasePolicy)


class ResourcePermission(Generic[PolicyT]):
    """
    A registered policy, and what is built from it.

    The bridges from a view to a policy hang off this: the DRF permission
    class, for one, is generated from the policy rather than written by hand.
    """

    def __init__(self, policy: PolicyT) -> None:
        self.policy = policy

    @property
    def key(self) -> str:
        """``loans.loan`` - the resource, as the registry knows it."""
        return f'{self.policy.app_label}.{self.policy.codename}'

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.key}: {type(self.policy).__name__}>'


class PermissionRegistry:
    """Holds one policy instance per resource."""

    def __init__(self) -> None:
        self._resources: dict[str, ResourcePermission[Any]] = {}
        self._defaults: dict[type[Model], ModelPolicy] = {}

    def register(self, policy_class: type[PolicyT]) -> ResourcePermission[PolicyT]:
        """
        Register a policy and return it, bound.

        Raises ``ImproperlyConfigured`` when the policy is not well formed, or
        when another policy already holds its resource.
        """
        policy_class.check_declaration()
        resource = ResourcePermission(policy_class())

        if resource.key in self._resources:
            holder = type(self._resources[resource.key].policy).__name__
            raise ImproperlyConfigured(
                f'{policy_class.__name__} claims {resource.key}, which {holder} already holds.'
            )

        self._resources[resource.key] = resource
        return resource

    def get(self, app_label: str, codename: str) -> ResourcePermission[Any] | None:
        return self._resources.get(f'{app_label}.{codename}')

    def policy_for(self, model: type[Model]) -> BasePolicy:
        """The policy registered for ``model``, or the model's own ``ModelPolicy``."""
        for resource in self._resources.values():
            policy: BasePolicy = resource.policy

            if policy.model is model:
                return policy

        if model not in self._defaults:
            self._defaults[model] = ModelPolicy.for_model(model)

        return self._defaults[model]

    def __contains__(self, key: object) -> bool:
        return key in self._resources

    def __iter__(self) -> Iterator[ResourcePermission[Any]]:
        return iter(self._resources.values())

    def __len__(self) -> int:
        return len(self._resources)


#: The project's registry. A test that registers policies makes its own.
registry = PermissionRegistry()
