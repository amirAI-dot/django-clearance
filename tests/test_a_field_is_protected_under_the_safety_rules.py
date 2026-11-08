"""
Protecting a field, and unprotecting it, obeys the same rules as every other
change to access.

If these fail, somebody who was never given a field unprotects it for
themselves, a field is protected that a scope rule reads - so the rule tells
whoever it reaches what the field holds - a field's permission is given with
a scope it cannot honour, or a field protected in code that cannot be is
found by a person refused, not at start-up.
"""

from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.dispatch import Signal
from django.test.utils import isolate_apps

from clearance import signals
from clearance.checks import check_models, field_errors
from clearance.fields import readable_fields
from clearance.models import ProtectedField, ScopeGrant, ScopeRule
from clearance.permissions import build_permissions
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment

AMOUNT_VIEW, AMOUNT_EDIT = 'lending.view_payment_amount', 'lending.change_payment_amount'

pytestmark = pytest.mark.django_db


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    make_user('clearance.permission_edit')  # somebody else who manages access
    return make_user(
        'clearance.permission_create', 'clearance.permission_edit', 'clearance.permission_delete'
    )


@pytest.fixture
def access(manager: Person) -> AccessService:
    return AccessService(actor=manager)


def stored(model: type[models.Model]) -> dict[str, str]:
    return dict(
        Permission.objects.filter(
            content_type=ContentType.objects.get_for_model(model), codename__contains='amount'
        ).values_list('codename', 'name')
    )


# ---------------------------------------------------------------- protecting


def test_protecting_a_field_makes_its_two_permissions(access: AccessService) -> None:
    marked = access.protect_field(Payment, 'amount')

    assert str(marked) == 'payment.amount'

    assert stored(Payment) == {
        'view_payment_amount': 'Can view amount of payments',
        'change_payment_amount': 'Can edit amount of payments',
    }


def test_once_protected_nobody_reads_it_until_given_it(
    access: AccessService, make_user: MakeUser
) -> None:
    person = make_user()
    access.protect_field(Payment, 'amount')

    assert 'amount' not in readable_fields(Person.objects.get(pk=person.pk), Payment)

    AccessService(actor=None).grant(person, AMOUNT_VIEW)  # the manager does not hold it
    assert 'amount' in readable_fields(Person.objects.get(pk=person.pk), Payment)


def test_protecting_needs_the_permission_to_create(make_user: MakeUser) -> None:
    with pytest.raises(AccessRefused):
        AccessService(actor=make_user('clearance.permission_edit')).protect_field(Payment, 'amount')


@pytest.mark.parametrize(
    ('model', 'field', 'message'),
    [
        (Payment, 'colour', 'Payment has no field'),
        (Loan, 'payments', 'a relation of another model'),
        (Payment, 'id', 'the primary key'),
        (Person, 'password', 'the password'),
        (Loan, 'credit_score', 'already protected'),
    ],
)
def test_a_field_that_cannot_be_protected_is_refused(
    access: AccessService, model: type[models.Model], field: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        access.protect_field(model, field)


def test_a_field_already_marked_is_not_marked_twice(access: AccessService) -> None:
    access.protect_field(Payment, 'amount')

    with pytest.raises(ValidationError, match='already protected'):
        access.protect_field(Payment, 'amount')


def test_a_field_a_scope_rule_reads_is_not_protected_until_the_rule_changes(
    access: AccessService,
) -> None:
    content_type = ContentType.objects.get_for_model(Payment)
    ScopeRule.objects.create(
        content_type=content_type,
        code='large',
        name='Large',
        conditions=[{'field': 'amount', 'operator': 'at_least', 'value': {'constant': 500}}],
    )
    ScopeRule.objects.create(  # already broken: not the field's doing, and not in the way
        content_type=content_type,
        code='broken',
        name='Broken',
        conditions=[{'field': 'gone', 'operator': 'is_empty'}],
    )

    with pytest.raises(ValidationError, match="read by the scope rules 'large'"):
        access.protect_field(Payment, 'amount')

    assert not ProtectedField.objects.exists()


# ---------------------------------------------------------------- unprotecting


def test_unprotecting_takes_away_its_permissions_and_every_grant_of_them(
    access: AccessService, make_user: MakeUser
) -> None:
    access.protect_field(Payment, 'amount')
    system = AccessService(actor=None)
    holder = make_user()
    system.grant(holder, AMOUNT_VIEW)
    system.grant(access.actor, AMOUNT_VIEW)  # type: ignore[arg-type]
    system.grant(access.actor, AMOUNT_EDIT)  # type: ignore[arg-type]

    access.unprotect_field(Payment, 'amount')

    assert stored(Payment) == {}
    assert not ProtectedField.objects.exists()
    assert not holder.user_permissions.exists()
    assert 'amount' in readable_fields(make_user(), Payment), 'everybody reads it again'


def test_nobody_unprotects_a_field_they_were_never_given(access: AccessService) -> None:
    access.protect_field(Payment, 'amount')

    with pytest.raises(AccessRefused) as refused:
        access.unprotect_field(Payment, 'amount')

    assert refused.value.rule == 'not_held'
    assert ProtectedField.objects.exists()


def test_the_superuser_unprotects_any_field(access: AccessService, make_user: MakeUser) -> None:
    access.protect_field(Payment, 'amount')

    AccessService(actor=make_user(superuser=True)).unprotect_field(Payment, 'amount')

    assert not ProtectedField.objects.exists()


def test_unprotecting_needs_the_permission_to_delete(
    access: AccessService, make_user: MakeUser
) -> None:
    access.protect_field(Payment, 'amount')

    with pytest.raises(AccessRefused):
        AccessService(actor=make_user('clearance.permission_create')).unprotect_field(
            Payment, 'amount'
        )


def test_a_field_protected_in_code_is_unprotected_in_code(access: AccessService) -> None:
    with pytest.raises(ValidationError, match='protected in code'):
        access.unprotect_field(Loan, 'credit_score')


def test_unprotecting_a_field_nobody_protected_changes_nothing(
    access: AccessService, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    with django_capture_on_commit_callbacks() as sent:
        access.unprotect_field(Payment, 'amount')

    assert sent == []


def test_protecting_and_unprotecting_is_announced(
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    caught: list[tuple[Signal, dict[str, Any]]] = []

    def receiver(signal: Signal, **kwargs: Any) -> None:
        caught.append((signal, kwargs))

    signals.field_protected.connect(receiver, weak=False)
    signals.field_unprotected.connect(receiver, weak=False)
    system = AccessService(actor=None)

    try:
        with django_capture_on_commit_callbacks(execute=True):
            system.protect_field(Payment, 'amount')
            system.unprotect_field(Payment, 'amount')
    finally:
        signals.field_protected.disconnect(receiver)
        signals.field_unprotected.disconnect(receiver)

    assert [(signal, kwargs['field'], kwargs['permissions']) for signal, kwargs in caught] == [
        (signals.field_protected, 'amount', {'view': AMOUNT_VIEW, 'edit': AMOUNT_EDIT}),
        (signals.field_unprotected, 'amount', {'view': AMOUNT_VIEW, 'edit': AMOUNT_EDIT}),
    ]


# ---------------------------------------------------------------- no scope on a field


def test_a_fields_permission_is_given_with_no_scope(make_user: MakeUser) -> None:
    system, person = AccessService(actor=None), make_user()

    with pytest.raises(ValidationError, match="a field's permission takes no scope"):
        system.grant(person, 'lending.loan_view_credit_score', 'own')

    with pytest.raises(ValidationError, match="a field's permission takes no scope"):
        system.create_bundle('Officers', {'lending.loan_edit_credit_score': 'all'})

    system.grant(person, 'lending.loan_view_credit_score')
    assert not ScopeGrant.objects.filter(permission=permission('lending.loan_view_credit_score'))


# ---------------------------------------------------------------- at start-up


@isolate_apps('tests.project.lending')
def test_a_field_protected_in_code_that_cannot_be_is_refused_at_start_up() -> None:
    class Overdraft(models.Model):
        limit = models.PositiveIntegerField()

        class Meta:
            app_label = 'lending'
            default_permissions = ()
            permissions = build_permissions(
                'overdraft', 'overdrafts', protected_fields=('limit', 'colour', 'id')
            )

        def __str__(self) -> str:
            return 'overdraft'

    errors = field_errors([Overdraft])

    assert [error.id for error in errors] == ['clearance.E012', 'clearance.E012']
    assert "'colour' in code, and cannot: Overdraft has no field" in errors[0].msg
    assert 'the primary key' in errors[1].msg


def test_the_project_protects_only_fields_that_can_be() -> None:
    assert check_models() == []
