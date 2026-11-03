"""
Every resource has one policy, and a policy that cannot work fails at start-up.

If these fail, a second policy can silently take over a resource from the
first, or a policy that maps an action to a hook it does not have starts
without complaint and refuses that action to everybody, for ever.
"""

from collections.abc import Mapping
from typing import ClassVar

import pytest
from django.core.exceptions import ImproperlyConfigured

from clearance.policies import BasePolicy
from clearance.registry import PermissionRegistry, ResourcePermission


class LoanPolicy(BasePolicy):
    app_label = 'lending'
    codename = 'loan'


@pytest.fixture
def registry() -> PermissionRegistry:
    return PermissionRegistry()


def test_registering_binds_one_instance_of_the_policy(registry: PermissionRegistry) -> None:
    resource = registry.register(LoanPolicy)

    assert isinstance(resource, ResourcePermission)
    assert isinstance(resource.policy, LoanPolicy)
    assert resource.key == 'lending.loan'
    assert repr(resource) == '<ResourcePermission lending.loan: LoanPolicy>'


def test_a_registered_resource_is_found_by_its_key(registry: PermissionRegistry) -> None:
    resource = registry.register(LoanPolicy)

    assert registry.get('lending', 'loan') is resource
    assert 'lending.loan' in registry
    assert list(registry) == [resource]
    assert len(registry) == 1


def test_a_resource_nobody_registered_is_not_found(registry: PermissionRegistry) -> None:
    assert registry.get('lending', 'loan') is None
    assert 'lending.loan' not in registry


def test_a_second_policy_for_the_same_resource_is_refused(registry: PermissionRegistry) -> None:
    class CopiedPolicy(BasePolicy):
        app_label = 'lending'
        codename = 'loan'

    registry.register(LoanPolicy)

    with pytest.raises(ImproperlyConfigured, match='LoanPolicy already holds'):
        registry.register(CopiedPolicy)


@pytest.mark.parametrize(('app_label', 'codename'), [('', 'loan'), ('lending', ''), ('', '')])
def test_a_policy_that_names_no_resource_is_refused(
    registry: PermissionRegistry, app_label: str, codename: str
) -> None:
    policy_class = type(
        'NamelessPolicy', (BasePolicy,), {'app_label': app_label, 'codename': codename}
    )

    with pytest.raises(ImproperlyConfigured, match='app_label and codename'):
        registry.register(policy_class)


def test_a_custom_action_mapped_to_a_missing_hook_is_refused(
    registry: PermissionRegistry,
) -> None:
    class ForgetfulPolicy(LoanPolicy):
        custom_actions: ClassVar[Mapping[str, str]] = {'approve': 'can_approve'}

    with pytest.raises(ImproperlyConfigured, match='can_approve'):
        registry.register(ForgetfulPolicy)


def test_a_custom_action_mapped_to_an_existing_hook_is_accepted(
    registry: PermissionRegistry,
) -> None:
    class ApprovingPolicy(LoanPolicy):
        custom_actions: ClassVar[Mapping[str, str]] = {'approve': 'can_edit'}

    assert registry.register(ApprovingPolicy).policy.custom_actions == {'approve': 'can_edit'}
