"""
A policy answers "may this person do this?" - by permission, then by object.

If these fail, somebody is let in who holds nothing, a rule about the object
is skipped because a hook was overridden, or a misspelled action is answered
with a guess instead of an error.
"""

from collections.abc import Mapping
from typing import ClassVar

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from clearance.policies import BasePolicy, SignedInReadPolicy
from clearance.protocols import User as AnyUser
from tests.conftest import MakeUser
from tests.project.lending.models import Loan


class LoanPolicy(BasePolicy):
    app_label = 'lending'
    codename = 'loan'
    custom_actions: ClassVar[Mapping[str, str]] = {'approve': 'can_approve'}

    def can_view(self, user: AnyUser, obj: object | None = None) -> bool:
        if not super().can_view(user, obj):
            return False
        return obj is None or getattr(obj, 'applicant_id', None) == getattr(user, 'pk', None)

    def can_approve(self, user: AnyUser, obj: object | None = None) -> bool:
        if not self.has(user, 'approve'):
            return False
        return obj is None or getattr(obj, 'applicant_id', None) != getattr(user, 'pk', None)


@pytest.fixture
def policy() -> LoanPolicy:
    return LoanPolicy()


def loan_for(person: User) -> Loan:
    return Loan.objects.create(applicant=person, amount=1000)


# ---------------------------------------------------------------- the permission


def test_a_hook_asks_for_the_resources_permission(policy: LoanPolicy) -> None:
    assert policy.permission_for('approve') == 'lending.loan_approve'


def test_listing_and_viewing_both_need_the_view_permission(
    policy: LoanPolicy, make_user: MakeUser
) -> None:
    reader = make_user('lending.loan_view')
    stranger = make_user()

    assert policy.allows(reader, 'list')
    assert policy.allows(reader, 'view')
    assert not policy.allows(stranger, 'list')
    assert not policy.allows(stranger, 'view')


@pytest.mark.parametrize('action', ['list', 'view', 'create', 'edit', 'delete', 'approve'])
def test_somebody_not_signed_in_may_do_nothing(
    policy: LoanPolicy, anonymous: AnonymousUser, action: str
) -> None:
    assert not policy.allows(anonymous, action)


def test_an_inactive_account_may_do_nothing_it_was_granted(
    policy: LoanPolicy, make_user: MakeUser
) -> None:
    gone = make_user('lending.loan_create', active=False)

    assert not policy.allows(gone, 'create')


def test_each_action_needs_its_own_permission(policy: LoanPolicy, make_user: MakeUser) -> None:
    editor = make_user('lending.loan_edit')

    assert policy.allows(editor, 'edit')
    assert not policy.allows(editor, 'create')
    assert not policy.allows(editor, 'delete')


def test_the_superuser_holds_every_permission(policy: LoanPolicy, make_user: MakeUser) -> None:
    root = make_user(superuser=True)

    assert all(policy.allows(root, action) for action in ('create', 'edit', 'delete', 'approve'))


# ---------------------------------------------------------------- the object


def test_an_overridden_hook_still_requires_the_permission(
    policy: LoanPolicy, make_user: MakeUser
) -> None:
    applicant = make_user()

    assert not policy.allows(applicant, 'view', loan_for(applicant))


def test_a_hook_judges_the_object_it_is_handed(policy: LoanPolicy, make_user: MakeUser) -> None:
    applicant = make_user('lending.loan_view')
    other = make_user('lending.loan_view')
    loan = loan_for(applicant)

    assert policy.allows(applicant, 'view', loan)
    assert not policy.allows(other, 'view', loan)


def test_a_custom_action_is_decided_by_its_own_hook(
    policy: LoanPolicy, make_user: MakeUser
) -> None:
    officer = make_user('lending.loan_approve')
    loan = loan_for(officer)

    assert policy.allows(officer, 'approve')
    assert not policy.allows(officer, 'approve', loan), 'nobody approves their own loan'
    assert policy.allows(officer, 'approve', loan_for(make_user()))


# ---------------------------------------------------------------- asking


def test_authorize_refuses_with_djangos_own_exception(
    policy: LoanPolicy, make_user: MakeUser
) -> None:
    with pytest.raises(PermissionDenied):
        policy.authorize(make_user(), 'approve')


def test_authorize_lets_through_whoever_is_allowed(policy: LoanPolicy, make_user: MakeUser) -> None:
    policy.authorize(make_user('lending.loan_approve'), 'approve')


def test_an_action_with_no_hook_is_an_error_not_an_answer(
    policy: LoanPolicy, make_user: MakeUser
) -> None:
    with pytest.raises(ImproperlyConfigured, match='can_aprove'):
        policy.allows(make_user(superuser=True), 'aprove')


# ---------------------------------------------------------------- reference data


class BranchPolicy(SignedInReadPolicy):
    app_label = 'lending'
    codename = 'loan'


def test_reference_data_is_read_by_anybody_signed_in(make_user: MakeUser) -> None:
    policy = BranchPolicy()
    member = make_user()

    assert policy.allows(member, 'list')
    assert policy.allows(member, 'view')


def test_reference_data_is_read_by_nobody_signed_out_or_inactive(
    make_user: MakeUser, anonymous: AnonymousUser
) -> None:
    policy = BranchPolicy()

    assert not policy.allows(anonymous, 'view')
    assert not policy.allows(make_user(active=False), 'view')


def test_reference_data_is_still_written_by_permission(make_user: MakeUser) -> None:
    policy = BranchPolicy()

    assert not policy.allows(make_user(), 'create')
    assert policy.allows(make_user('lending.loan_create'), 'create')
