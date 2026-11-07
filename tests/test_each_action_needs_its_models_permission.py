"""
Every action on a model needs the permission that model keeps - Django's or its own.

If these fail, a model left to the default asks for a permission migrate
never made, so nobody can ever be given it; or a model with its own asks for
Django's, which it switched off; or a model with no policy is not asked at
all.
"""

import pytest

from clearance.permissions import permission_for
from clearance.policies import BasePolicy, ModelPolicy
from clearance.registry import PermissionRegistry, registry
from tests.conftest import MakeUser
from tests.project.lending.models import Loan, Payment
from tests.project.lending.policies import LoanPolicy


@pytest.mark.parametrize(
    ('action', 'expected'),
    [
        ('view', 'lending.view_payment'),
        ('list', 'lending.view_payment'),
        ('create', 'lending.add_payment'),
        ('edit', 'lending.change_payment'),
        ('delete', 'lending.delete_payment'),
        ('refund', 'lending.payment_refund'),
    ],
)
def test_a_model_keeping_djangos_permissions_is_asked_in_djangos_words(
    action: str, expected: str
) -> None:
    assert permission_for(Payment, action) == expected


@pytest.mark.parametrize(
    ('action', 'expected'),
    [
        ('view', 'lending.loan_view'),
        ('list', 'lending.loan_view'),
        ('edit', 'lending.loan_edit'),
        ('approve', 'lending.loan_approve'),
    ],
)
def test_a_model_declaring_its_own_is_asked_in_its_own(action: str, expected: str) -> None:
    assert permission_for(Loan, action) == expected


def test_a_resource_named_otherwise_than_its_model_is_asked_by_that_name() -> None:
    assert permission_for(Loan, 'edit', codename='credit') == 'lending.credit_edit'


def test_an_instance_is_asked_like_its_model(make_user: MakeUser) -> None:
    loan = Loan(applicant=make_user(), amount=1)

    assert permission_for(loan, 'view') == 'lending.loan_view'


# ---------------------------------------------------------------- whose policy


def test_a_model_with_no_policy_is_asked_through_its_own_model_policy() -> None:
    policy = registry.policy_for(Payment)

    assert isinstance(policy, ModelPolicy)
    assert policy.permission_for('edit') == 'lending.change_payment'
    assert registry.policy_for(Payment) is policy, 'made once'


def test_a_model_with_a_policy_is_asked_through_it() -> None:
    assert isinstance(registry.policy_for(Loan), LoanPolicy)


def test_a_policy_naming_a_model_by_its_labels_asks_in_that_models_words() -> None:
    class PaymentPolicy(BasePolicy):
        app_label = 'lending'
        codename = 'payment'

    own = PermissionRegistry()
    policy = own.register(PaymentPolicy).policy

    assert policy.model is Payment
    assert policy.permission_for('edit') == 'lending.change_payment'
    assert own.policy_for(Payment) is policy


def test_a_policy_for_no_model_keeps_its_own_words() -> None:
    class ReportPolicy(BasePolicy):
        app_label = 'reporting'
        codename = 'report'

    policy = PermissionRegistry().register(ReportPolicy).policy

    assert policy.model is None
    assert policy.permission_for('list') == 'reporting.report_view'
