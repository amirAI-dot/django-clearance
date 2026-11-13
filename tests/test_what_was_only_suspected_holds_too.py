"""
What the 0.1.0 review suspected and had not proved - proved here, and held.

If these fail, a boolean sent as a form sends it is refused to whoever may
write it, a rule on a generic relation is a server error, a field's
permission is another model's by having its name, a malformed ``ACCESS`` file
fails with a traceback, two administrators at once leave nobody managing
access, undoing a migration loses every rule, and an API takes a related row
the person may not see.
"""

import contextlib
from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from clearance.checks import field_errors
from clearance.declared import access_problems, sync_after_migrate
from clearance.models import ScopeRule, StatusAction
from clearance.permissions import build_permissions
from clearance.rules import Rule
from clearance.services import AccessService
from clearance.writes import refused_writes
from tests.conftest import MakeBundle, MakeUser
from tests.project.lending.models import Loan, Payment, Statement

pytestmark = pytest.mark.django_db

EDITOR = (('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))


def content_type(model: type[models.Model]) -> ContentType:
    return ContentType.objects.get_for_model(model)


@contextlib.contextmanager
def a_model_of_the_moment(name: str) -> Iterator[None]:
    """A model made inside a test is taken out of the app registry after it."""
    try:
        yield
    finally:
        del apps.all_models['lending'][name]
        apps.clear_cache()


# ---------------------------------------------------------------------- values


@pytest.mark.parametrize('sent', ['true', 'on', 'True', '1', True])
def test_a_yes_is_a_yes_however_a_form_sends_it(make_user: MakeUser, sent: object) -> None:
    AccessService(actor=None).create_status_action(
        Loan, 'settle', 'Settle', 'approved', [True], [False]
    )
    loan = Loan.objects.create(applicant=make_user(), amount=1)
    clerk = make_user(*EDITOR)
    officer = make_user(*EDITOR, ('lending.loan_settle', 'all'))

    assert refused_writes(officer, Loan, {'approved': sent}, loan) == {}
    assert list(refused_writes(clerk, Loan, {'approved': sent}, loan)) == ['approved']


# ---------------------------------------------------------------------- rules


def test_a_rule_on_a_generic_relation_is_refused_rather_than_failing(db: None) -> None:
    with a_model_of_the_moment('note'):

        class Note(models.Model):
            content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
            object_id = models.PositiveIntegerField()
            about = GenericForeignKey()

            class Meta:
                app_label = 'lending'

            def __str__(self) -> str:
                return f'A note about {self.about}'

        with pytest.raises(ValidationError, match='about'):
            Rule.parse(
                Note, 'all', [{'field': 'about', 'operator': 'is', 'value': {'constant': 1}}]
            )


# ---------------------------------------------------------------------- permissions


def test_a_field_is_not_protected_by_a_permission_another_model_has(db: None) -> None:
    """``has_perm`` knows a permission by its app and its codename: two models' would be one."""
    Permission.objects.create(
        content_type=content_type(Loan), codename='view_statement_region', name='Of another model'
    )

    with pytest.raises(ValidationError, match='view_statement_region'):
        AccessService(actor=None).protect_field(Statement, 'region')


def test_a_status_action_is_not_made_with_a_permission_another_model_has(db: None) -> None:
    Permission.objects.create(
        content_type=content_type(Loan), codename='payment_refund', name='Of another model'
    )

    with pytest.raises(ValidationError, match='payment_refund'):
        AccessService(actor=None).create_status_action(
            Payment, 'refund', 'Refund', 'state', ['refunded']
        )

    assert not StatusAction.objects.exists()


def test_a_field_protected_in_code_with_another_models_permission_fails_at_start_up() -> None:
    with a_model_of_the_moment('ledger'), a_model_of_the_moment('ledgerviewtotal'):

        class Ledger(models.Model):
            total = models.PositiveIntegerField()

            class Meta:
                app_label = 'lending'
                default_permissions = ()
                permissions = build_permissions('ledger', 'ledgers', protected_fields=('total',))

            def __str__(self) -> str:
                return f'Ledger {self.pk}'

        class LedgerViewTotal(models.Model):
            class Meta:
                app_label = 'lending'
                default_permissions = ()
                permissions = (('ledger_view_total', 'Can view the totals of ledgers'),)

            def __str__(self) -> str:
                return f'A view of totals {self.pk}'

        errors = field_errors([Ledger, LedgerViewTotal])

    assert [error.id for error in errors] == ['clearance.E012']
    assert 'lending.ledger_view_total' in errors[0].msg
    assert field_errors([Loan, Payment, Statement]) == []


# ---------------------------------------------------------------------- access as code


@pytest.mark.parametrize(
    'spec',
    [
        {'field': 'status', 'to': 5},
        {'field': 'status', 'to': 'approved'},
        {'field': 'status', 'to': ['approved'], 'from': 'pending'},
        {'field': 7, 'to': ['approved']},
    ],
)
def test_a_malformed_status_action_in_the_file_is_a_problem_said(spec: dict[str, Any]) -> None:
    problems = access_problems({'status_actions': {'lending.Loan': {'sign': spec}}})

    assert len(problems) == 1
    assert problems[0].startswith('status_actions: lending.Loan.sign: ')


@override_settings(CLEARANCE={'SYNC_ON_MIGRATE': True})
def test_a_sync_skipped_on_a_test_database_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    """A database named ``test_...`` in production would otherwise never sync, and never say."""
    last = list(apps.get_app_configs())[-1]

    sync_after_migrate(sender=last, verbosity=1)

    assert 'clearance_sync: skipped' in capsys.readouterr().out


# ---------------------------------------------------------------------- two at once


@pytest.mark.skipif(
    not connection.features.has_select_for_update, reason='SQLite writes one at a time'
)
def test_a_change_that_could_leave_nobody_managing_waits_its_turn(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    """Two administrators taking it from each other at once would each see the other still there."""
    managers = make_bundle({'clearance.permission_edit': None})
    person = make_user(bundles=(managers,))
    make_user(bundles=(managers,))

    with CaptureQueriesContext(connection) as queries:
        AccessService(actor=None).take_bundle(person, managers)

    assert any('FOR UPDATE' in query['sql'] for query in queries)


# ---------------------------------------------------------------------- migrations


@pytest.mark.django_db(transaction=True)
def test_the_rows_of_rules_and_actions_go_back_into_their_columns() -> None:
    """Undoing 0006 left every rule with no condition and every action with no value."""
    newest = MigrationExecutor(connection).loader.graph.leaf_nodes()
    conditions = [
        {'field': 'region', 'operator': 'is_one_of', 'value': {'constant': ['north', 'south']}},
        {'field': 'applicant', 'operator': 'is', 'value': {'person': ''}},
        {'field': 'officer', 'operator': 'is_empty'},
    ]
    access = AccessService(actor=None)
    access.create_scope_rule(Loan, 'mine', 'Mine', conditions, match='any')
    access.create_status_action(Payment, 'refund', 'Refund', 'state', ['refunded'], ['paid'])

    try:
        MigrationExecutor(connection).migrate([('clearance', '0005_declared')])
        before = MigrationExecutor(connection).loader.project_state(
            [('clearance', '0005_declared')]
        )
        rule = before.apps.get_model('clearance', 'ScopeRule').objects.get()
        action = before.apps.get_model('clearance', 'StatusAction').objects.get()

        assert rule.conditions == conditions
        assert (action.to_values, action.from_values) == (['refunded'], ['paid'])

        # A condition that compared with nothing is "is empty", once it is a row.
        rule.conditions = [{'field': 'officer', 'operator': 'is', 'value': {'constant': None}}]
        rule.save()
    finally:
        MigrationExecutor(connection).migrate(newest)

    assert ScopeRule.objects.get().conditions == [{'field': 'officer', 'operator': 'is_empty'}]
    assert StatusAction.objects.get().to_values == ['refunded']


# ---------------------------------------------------------------------- related rows


def test_an_api_takes_only_the_related_rows_the_person_may_view(make_user: MakeUser) -> None:
    their_loan = Loan.objects.create(applicant=make_user(), amount=100)
    clerk = make_user(  # every payment is theirs to make, and no loan theirs to see
        ('lending.view_payment', 'all'),
        ('lending.add_payment', 'all'),
        ('lending.loan_view', 'own'),
    )
    my_loan = Loan.objects.create(applicant=clerk, amount=100)
    client = APIClient()
    client.force_authenticate(clerk)

    refused = client.post('/api/payments/', {'loan': their_loan.pk, 'amount': 5}, format='json')
    made = client.post('/api/payments/', {'loan': my_loan.pk, 'amount': 5}, format='json')

    assert (refused.status_code, made.status_code) == (400, 201)
    assert list(refused.json()) == ['loan']
    assert [payment.loan for payment in Payment.objects.all()] == [my_loan]
