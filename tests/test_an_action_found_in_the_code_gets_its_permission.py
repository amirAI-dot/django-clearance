"""
An action a view asks for, with no code deciding it, gets its permission on
migrate - and nobody holds it until given.

If these fail, a project has to declare by hand the permission of every page
that prints or exports, an administrator cannot give one out because it does
not exist, or a permission is made for an action nothing checks.
"""

import logging
from collections.abc import Iterator
from typing import Any

import pytest
from django.contrib.auth.models import Permission
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings
from django.urls import path

from clearance import signals
from clearance.checks import check_actions
from clearance.decorators import policy_required
from clearance.discovery import (
    ActionFinder,
    FoundAction,
    ViewFinder,
    action_problems,
    find_actions,
    make_found_permissions,
    make_permissions_after_migrate,
)
from clearance.policies import BasePolicy
from tests.conftest import MakeUser
from tests.project.lending.models import Loan, Statement
from tests.project.lending.policies import LoanPolicy, loan_access

pytestmark = pytest.mark.django_db

FOUND = {'lending.statement_print', 'lending.loan_export'}


class LedgerPolicy(BasePolicy):
    """A resource that is not one model: there is nowhere to keep a permission."""

    app_label = 'lending'
    codename = 'ledger'


LedgerPolicy.check_declaration()


@policy_required(LedgerPolicy(), 'reconcile')
def reconcile(request: HttpRequest) -> HttpResponse:
    return HttpResponse()


def about(request: HttpRequest) -> HttpResponse:
    return HttpResponse()


#: A URLconf for the tests below: an action with nowhere to keep its permission, and a page
#: that asks no policy at all.
urlpatterns = [path('reconcile/', reconcile), path('about/', about)]


def found_permissions() -> set[str]:
    return {action.permission for action in find_actions()}


# ---------------------------------------------------------------- what is found


def test_the_actions_views_ask_for_are_found() -> None:
    assert found_permissions() == FOUND


def test_neither_the_four_every_model_has_nor_an_action_with_a_hook_is_found() -> None:
    found = {action.action for action in find_actions()}

    assert not found & {'view', 'list', 'create', 'edit', 'delete'}
    assert 'approve' not in found, 'LoanPolicy decides it with can_approve'


def test_each_action_is_found_once_with_where_it_was_found() -> None:
    class Twice(ActionFinder):
        def find(self) -> Iterator[FoundAction]:
            yield from ViewFinder().find()
            yield FoundAction(loan_access.policy, 'export', 'elsewhere')
            yield FoundAction(loan_access.policy, 'Export!', 'nowhere')

    found = find_actions([Twice()])

    assert sorted(action.origin for action in found) == [
        'tests.project.lending.views.StatementPrintView',
        'tests.project.lending.views.export',
    ]


# ---------------------------------------------------------------- made on migrate


def test_migrate_made_their_permissions() -> None:
    names = dict(
        Permission.objects.filter(codename__in=['statement_print', 'loan_export']).values_list(
            'codename', 'name'
        )
    )

    assert names == {'statement_print': 'Can print statements', 'loan_export': 'Can export loans'}


def test_making_them_again_makes_nothing_new() -> None:
    assert make_found_permissions(find_actions()) == []

    Permission.objects.filter(codename='loan_export').delete()
    assert make_found_permissions(find_actions()) == ['lending.loan_export']


def test_what_migrate_made_is_announced(capsys: pytest.CaptureFixture[str]) -> None:
    Permission.objects.filter(codename__in=['statement_print', 'loan_export']).delete()
    caught: list[dict[str, Any]] = []

    def receiver(**kwargs: Any) -> None:
        caught.append(kwargs)

    signals.actions_found.connect(receiver, weak=False)

    try:
        make_permissions_after_migrate(sender=None, verbosity=2)
        make_permissions_after_migrate(sender=None, verbosity=2)  # nothing new: nothing sent
    finally:
        signals.actions_found.disconnect(receiver)

    assert [set(kwargs['permissions']) for kwargs in caught] == [FOUND]
    assert 'lending.loan_export' in capsys.readouterr().out


@override_settings(ROOT_URLCONF='not.a.module')
def test_a_urlconf_that_does_not_import_makes_nothing_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger='clearance'):
        make_permissions_after_migrate(sender=None)

    assert 'the URLconf could not be read' in caplog.text
    assert check_actions() == [], "Django's own check reports it"


# ---------------------------------------------------------------- held by nobody until given


def test_an_action_found_on_a_page_is_held_by_nobody_until_given(
    client: Client, make_user: MakeUser
) -> None:
    applicant = make_user()
    statement = Statement.objects.create(
        loan=Loan.objects.create(applicant=applicant, amount=1), total=1
    )
    address = f'/loans/statements/{statement.pk}/print/'

    client.force_login(make_user('lending.view_statement'))
    assert client.get(address).status_code == 403

    client.force_login(make_user('lending.statement_print'))
    assert client.get(address).content == f'statement:{statement.pk}'.encode()


def test_an_action_found_on_a_function_view_is_held_by_nobody_until_given(
    client: Client, make_user: MakeUser
) -> None:
    client.force_login(make_user('lending.loan_view'))
    assert client.get('/loans/export/').status_code == 403

    client.force_login(make_user('lending.loan_export'))
    assert client.get('/loans/export/').content == b'exported'


# ---------------------------------------------------------------- what cannot be made


def test_an_action_whose_policy_has_no_model_is_refused_at_start_up() -> None:
    with override_settings(
        ROOT_URLCONF='tests.test_an_action_found_in_the_code_gets_its_permission'
    ):
        errors = check_actions()
        assert make_found_permissions(find_actions()) == []

    assert [error.id for error in errors] == ['clearance.E013']
    assert 'has no model to keep the permission on' in errors[0].msg
    assert check_actions() == [], 'the project itself is configured right'


def test_an_action_too_long_to_be_a_permission_is_refused() -> None:
    action = FoundAction(LoanPolicy(), 'x' * 100, 'somewhere')

    assert 'longer than a permission can be' in (action_problems(action) or '')
    assert make_found_permissions([action]) == []


def test_a_page_that_asks_no_policy_has_no_action_to_find() -> None:
    with override_settings(
        ROOT_URLCONF='tests.test_an_action_found_in_the_code_gets_its_permission'
    ):
        assert [action.origin for action in ViewFinder().find()] == [
            'tests.test_an_action_found_in_the_code_gets_its_permission.reconcile'
        ]
