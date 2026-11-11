"""
A status action alone writes the values it claims - in code, in a form, and
when an administrator makes, changes or deletes one.

If these fail, a customer who may edit their own loan approves it by
choosing "approved" from the list, an officer approves a loan already
declined, or an administrator releases "refunded" to everybody who edits a
payment without ever having been allowed to refund one.
"""

from collections.abc import Callable
from typing import Any

import pytest
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.dispatch import Signal
from django.test import Client
from django.test.utils import isolate_apps
from pytest_django import DjangoAssertNumQueries

from clearance import signals
from clearance.actions import status_actions_of, writable_values
from clearance.checks import check_models, status_action_errors
from clearance.forms import ProtectedFieldsFormMixin, _offered
from clearance.models import ProtectedField, StatusAction
from clearance.permissions import build_permissions, declared_status_actions
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

EVERY_STATUS = frozenset({'pending', 'approved', 'declined'})
EDITOR = (('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))


class LoanStatusForm(ProtectedFieldsFormMixin, forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Loan
        fields = ('status', 'approved')


def fresh(person: Person) -> Person:
    return Person.objects.get(pk=person.pk)


@pytest.fixture
def loan(make_user: MakeUser) -> Loan:
    return Loan.objects.create(applicant=make_user(), amount=100)


@pytest.fixture
def payment(loan: Loan) -> Payment:
    return Payment.objects.create(loan=loan, amount=10, state='paid')


@pytest.fixture
def refund(payment: Payment) -> StatusAction:
    return AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded'], ['paid']
    )


# ---------------------------------------------------------------- declaring


def test_a_status_action_in_code_is_an_action_with_a_permission() -> None:
    declared = build_permissions(
        'loan',
        'loans',
        actions=('view',),
        status_actions={'approve': {'field': 'status', 'to': ['approved']}},
    )

    assert list(declared) == [
        ('loan_view', 'Can view loans'),
        ('loan_approve', 'Can approve loans'),
    ]
    assert dict(declared.status_actions['approve']) == {
        'field': 'status',
        'to': ('approved',),
        'from': (),
    }


def test_a_status_action_listed_as_an_action_too_is_one_permission() -> None:
    declared = build_permissions(
        'loan', 'loans', actions=('approve',), status_actions={'approve': {'field': 's', 'to': [1]}}
    )

    assert [codename for codename, _ in declared] == ['loan_approve']


@pytest.mark.parametrize(
    ('raw', 'message'),
    [
        ('approved', "give it 'field', 'to'"),
        ({'field': 'status', 'to': ['approved'], 'when': 'never'}, "give it 'field', 'to'"),
        ({'to': ['approved']}, 'name its field'),
        ({'field': 'status', 'to': []}, "'to' is a list"),
        ({'field': 'status', 'to': ['approved'], 'from': 'pending'}, "'from' is a list"),
    ],
)
def test_a_status_action_in_code_of_the_wrong_shape_is_refused_where_it_is_declared(
    raw: object, message: str
) -> None:
    with pytest.raises(ImproperlyConfigured, match=message):
        build_permissions('loan', 'loans', status_actions={'approve': raw})  # type: ignore[dict-item]


def test_what_code_declares_is_read_back_from_the_model() -> None:
    assert set(declared_status_actions(Loan)) == {'approve'}
    assert declared_status_actions(Payment) == {}


@isolate_apps('tests.project.lending')
def test_a_status_action_in_code_that_cannot_work_is_refused_at_start_up() -> None:
    class Cheque(models.Model):
        state = models.CharField(max_length=8, choices=(('new', 'New'), ('paid', 'Paid')))
        memo = models.CharField(max_length=8)

        class Meta:
            app_label = 'lending'
            default_permissions = ()
            permissions = build_permissions(
                'cheque',
                'cheques',
                status_actions={
                    'pay': {'field': 'state', 'to': ['paid'], 'from': ['lost']},
                    'sign': {'field': 'memo', 'to': ['x']},
                    'stamp': {'field': 'colour', 'to': ['x']},
                    'edit': {'field': 'state', 'to': ['new']},
                },
            )

        def __str__(self) -> str:
            return 'cheque'

    messages = [error.msg for error in status_action_errors([Cheque])]

    assert {error.id for error in status_action_errors([Cheque])} == {'clearance.E015'}
    assert messages == [
        "lending.Cheque, status action 'pay': 'lost' is not one of the values of Cheque.state.",
        "lending.Cheque, status action 'sign': Cheque.memo has no choices, and is not yes or no.",
        "lending.Cheque, status action 'stamp': Cheque has no field 'colour'.",
        "lending.Cheque, status action 'edit': 'edit' is an action every model has already.",
    ]


def test_the_project_declares_only_status_actions_that_work() -> None:
    assert check_models() == []


# ---------------------------------------------------------------- the values


def test_without_the_action_its_values_are_not_written(make_user: MakeUser, loan: Loan) -> None:
    assert writable_values(make_user(*EDITOR), Loan, 'status', loan) == {'pending'}


def test_with_the_action_its_values_are_written(make_user: MakeUser, loan: Loan) -> None:
    approver = make_user(*EDITOR, ('lending.loan_approve', 'all'))

    assert writable_values(approver, Loan, 'status', loan) == EVERY_STATUS


def test_an_action_writes_only_from_its_starting_values(make_user: MakeUser, loan: Loan) -> None:
    Loan.objects.filter(pk=loan.pk).update(status='declined')
    loan.refresh_from_db()
    approver = make_user(*EDITOR, ('lending.loan_approve', 'all'))

    assert writable_values(approver, Loan, 'status', loan) == {'pending', 'declined'}, (
        'pending nobody claims; declined it holds already; approved only from pending'
    )


def test_an_action_is_asked_of_the_policy_with_the_row(make_user: MakeUser, loan: Loan) -> None:
    officer = make_user(*EDITOR, ('lending.loan_approve', 'reviewing'))
    assert writable_values(officer, Loan, 'status', loan) == {'pending'}, 'not a loan they review'

    Loan.objects.filter(pk=loan.pk).update(officer=officer)
    loan.refresh_from_db()
    assert writable_values(fresh(officer), Loan, 'status', loan) == EVERY_STATUS

    own = Loan.objects.create(applicant=officer, officer=officer, amount=1)
    assert writable_values(fresh(officer), Loan, 'status', own) == {'pending'}, 'not their own'


def test_a_new_row_starts_from_the_fields_default(make_user: MakeUser) -> None:
    approver = make_user(('lending.loan_approve', 'all'))

    assert writable_values(approver, Loan, 'status') == EVERY_STATUS
    assert writable_values(approver, Loan, 'status', Loan(amount=1)) == EVERY_STATUS


def test_the_superuser_writes_every_value(make_user: MakeUser, loan: Loan) -> None:
    assert writable_values(make_user(superuser=True), Loan, 'status', loan) == EVERY_STATUS


def test_nobody_writes_a_value_of_a_field_they_may_not_write(
    make_user: MakeUser, loan: Loan
) -> None:
    ProtectedField.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), field='status'
    )

    assert writable_values(make_user(*EDITOR), Loan, 'status', loan) == frozenset()


def test_a_field_with_no_values_to_choose_from_has_no_answer(make_user: MakeUser) -> None:
    with pytest.raises(ValueError, match=r'Loan\.amount has no values'):
        writable_values(make_user(), Loan, 'amount')


def test_a_field_no_action_claims_is_every_value(make_user: MakeUser, payment: Payment) -> None:
    assert writable_values(make_user(), Payment, 'state', payment) == {'due', 'paid', 'refunded'}


def test_an_action_held_outside_the_rows_scope_does_not_reach_it(
    make_user: MakeUser, payment: Payment, refund: StatusAction
) -> None:
    holder = make_user('lending.payment_refund')  # no scope: payments' default is their own

    assert writable_values(holder, Payment, 'state', payment) == {'due', 'paid'}


def test_a_status_action_made_in_the_database_claims_its_values(
    make_user: MakeUser, payment: Payment, refund: StatusAction
) -> None:
    holder = make_user(('lending.payment_refund', 'all'))

    assert writable_values(make_user(), Payment, 'state', payment) == {'due', 'paid'}
    assert writable_values(holder, Payment, 'state', payment) == {'due', 'paid', 'refunded'}

    due = Payment.objects.create(loan=payment.loan, amount=1, state='due')
    assert writable_values(holder, Payment, 'state', due) == {'due', 'paid'}, 'only from paid'


def test_a_status_action_whose_field_is_gone_claims_nothing(
    make_user: MakeUser, payment: Payment
) -> None:
    StatusAction.objects.create(
        content_type=ContentType.objects.get_for_model(Payment),
        code='void',
        name='Void',
        field='gone',
        to_values=['x'],
    )

    assert status_actions_of(make_user()).fields(Payment) == frozenset()


def test_status_actions_are_read_once_per_request(
    make_user: MakeUser,
    loan: Loan,
    refund: StatusAction,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    person = fresh(make_user(*EDITOR))

    with django_assert_num_queries(1):
        status_actions_of(person)
        status_actions_of(person)


# ---------------------------------------------------------------- a form


def test_a_form_offers_only_the_values_the_person_may_write(
    make_user: MakeUser, loan: Loan
) -> None:
    form = LoanStatusForm(instance=loan, user=make_user(*EDITOR))

    assert [value for value, _ in form.fields['status'].choices] == ['pending']  # type: ignore[attr-defined]


def test_a_form_refuses_a_value_sent_past_what_it_offered(make_user: MakeUser, loan: Loan) -> None:
    form = LoanStatusForm({'status': 'approved'}, instance=loan, user=make_user(*EDITOR))

    assert not form.is_valid()
    assert 'status' in form.errors


def test_a_yes_or_no_field_is_refused_when_the_value_is_not_theirs(
    make_user: MakeUser, loan: Loan
) -> None:
    AccessService(actor=None).create_status_action(Loan, 'sign_off', 'Sign off', 'approved', [True])

    refused = LoanStatusForm(
        {'status': 'pending', 'approved': 'on'}, instance=loan, user=make_user()
    )
    assert not refused.is_valid()
    assert refused.errors['approved'] == ['You may not set approved to True.']

    allowed = LoanStatusForm(
        {'status': 'pending', 'approved': 'on'},
        instance=loan,
        user=make_user(('lending.loan_sign_off', 'all')),
    )
    assert allowed.is_valid(), allowed.errors


def test_grouped_choices_keep_their_groups_and_lose_what_is_not_allowed() -> None:
    choices = [('', '---'), ('Open', [('a', 'A'), ('b', 'B')]), ('Closed', [('c', 'C')])]

    assert list(_offered(choices, frozenset({'a'}))) == [('', '---'), ('Open', [('a', 'A')])]


def test_a_page_offers_and_saves_only_what_the_person_may_write(
    client: Client, make_user: MakeUser, loan: Loan
) -> None:
    sent = {'amount': 100, 'region': '', 'status': 'approved'}
    client.force_login(make_user(*EDITOR))

    assert 'value="approved"' not in client.get(f'/loans/{loan.pk}/edit/').content.decode()
    assert client.post(f'/loans/{loan.pk}/edit/', sent).status_code == 200, 'shown again'

    client.force_login(make_user(*EDITOR, ('lending.loan_approve', 'all')))
    assert client.post(f'/loans/{loan.pk}/edit/', sent).status_code == 302
    loan.refresh_from_db()
    assert loan.status == 'approved'


# ---------------------------------------------------------------- made by an administrator


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    make_user('clearance.permission_edit')  # somebody else who manages access
    return make_user(
        'clearance.permission_create', 'clearance.permission_edit', 'clearance.permission_delete'
    )


@pytest.fixture
def access(manager: Person) -> AccessService:
    return AccessService(actor=manager)


def test_making_a_status_action_makes_its_permission(access: AccessService) -> None:
    action = access.create_status_action(Payment, 'refund', 'Refund', 'state', ['refunded'])

    assert permission('lending.payment_refund').name == 'Can refund payments'
    assert str(action) == 'payment: Refund'


def test_making_one_needs_the_permission_to_create(make_user: MakeUser) -> None:
    with pytest.raises(AccessRefused):
        AccessService(actor=make_user('clearance.permission_edit')).create_status_action(
            Payment, 'refund', 'Refund', 'state', ['refunded']
        )


@pytest.mark.parametrize(
    ('model', 'code', 'field', 'to', 'message'),
    [
        (Payment, 'Refund!', 'state', ['refunded'], 'is not an action'),
        (Payment, 'edit', 'state', ['refunded'], 'every model has already'),
        (Payment, 'refund', 'colour', ['refunded'], 'Payment has no field'),
        (Payment, 'refund', 'amount', [1], 'has no choices'),
        (Payment, 'refund', 'state', ['lost'], "'lost' is not one of the values"),
        (Payment, 'refund', 'state', [], 'writes no value'),
        (Loan, 'sign_off', 'approved', ['maybe'], "'maybe' is not one of the values"),
        (Loan, 'approve', 'status', ['approved'], 'an action Loan has already'),
        (Loan, 'export', 'status', ['approved'], 'an action Loan has already'),
    ],
)
def test_a_status_action_that_cannot_work_is_refused(
    access: AccessService,
    model: type[models.Model],
    code: str,
    field: str,
    to: list[Any],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        access.create_status_action(model, code, 'Anything', field, to)


def test_renaming_or_claiming_more_is_open_to_whoever_may_edit(
    access: AccessService, refund: StatusAction
) -> None:
    access.change_status_action(refund, name='Give back', to=['refunded', 'due'])

    refund.refresh_from_db()
    assert (refund.name, refund.to_values) == ('Give back', ['refunded', 'due'])


def test_a_value_is_released_only_by_whoever_may_act_on_every_row(
    access: AccessService, refund: StatusAction
) -> None:
    access.change_status_action(refund, to=['refunded', 'due'])

    with pytest.raises(AccessRefused) as refused:
        access.change_status_action(refund, to=['refunded'])
    assert refused.value.rule == 'not_held'

    AccessService(actor=None).grant(access.actor, 'lending.payment_refund', 'all')  # type: ignore[arg-type]
    access.change_status_action(refund, to=['refunded'])


def test_nobody_lets_an_action_they_hold_write_from_more_values(
    access: AccessService, refund: StatusAction
) -> None:
    AccessService(actor=None).grant(access.actor, 'lending.payment_refund', 'all')  # type: ignore[arg-type]

    for start in (['paid', 'due'], []):
        with pytest.raises(AccessRefused) as refused:
            access.change_status_action(refund, start=start)
        assert refused.value.rule == 'own_action'

    access.change_status_action(refund, start=['paid'])  # no wider: allowed


def test_somebody_not_holding_it_widens_where_it_writes_from(
    access: AccessService, refund: StatusAction
) -> None:
    access.change_status_action(refund, start=[])

    refund.refresh_from_db()
    assert refund.from_values == []


def test_a_change_that_cannot_work_is_refused(access: AccessService, refund: StatusAction) -> None:
    with pytest.raises(ValidationError, match='writes no value'):
        access.change_status_action(refund, to=[])


def test_deleting_one_takes_its_permission_and_needs_it_on_every_row(
    access: AccessService, refund: StatusAction, make_user: MakeUser
) -> None:
    with pytest.raises(AccessRefused):
        access.delete_status_action(refund)

    AccessService(actor=None).grant(access.actor, 'lending.payment_refund', 'all')  # type: ignore[arg-type]
    access.delete_status_action(refund)

    assert not StatusAction.objects.exists()
    assert not ContentType.objects.get_for_model(Payment).permission_set.filter(
        codename='payment_refund'
    )


def test_making_changing_and_deleting_is_announced(
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    caught: list[tuple[Signal, dict[str, Any]]] = []

    def receiver(signal: Signal, **kwargs: Any) -> None:
        caught.append((signal, kwargs))

    signals.status_action_saved.connect(receiver, weak=False)
    signals.status_action_deleted.connect(receiver, weak=False)
    system = AccessService(actor=None)

    try:
        with django_capture_on_commit_callbacks(execute=True):
            action = system.create_status_action(Payment, 'refund', 'Refund', 'state', ['refunded'])
            system.change_status_action(action, name='Give back')
            system.delete_status_action(action)
    finally:
        signals.status_action_saved.disconnect(receiver)
        signals.status_action_deleted.disconnect(receiver)

    assert [(signal, kwargs.get('created', kwargs.get('code'))) for signal, kwargs in caught] == [
        (signals.status_action_saved, True),
        (signals.status_action_saved, False),
        (signals.status_action_deleted, 'refund'),
    ]
