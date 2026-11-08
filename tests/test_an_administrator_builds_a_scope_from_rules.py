"""
An administrator builds a row scope from rules, and it reaches exactly those rows.

If these fail, a scope built in the admin site reaches rows its conditions do
not describe, a rule that cannot work is saved anyway, a rule reads a field
its writer may not see, or a model with no access code at all cannot be
scoped.
"""

import datetime
import logging
from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Model, UUIDField
from django.dispatch import Signal
from django.test import override_settings
from pytest_django import DjangoAssertNumQueries

from clearance import rules, signals
from clearance.models import ScopeGrant, ScopeRule
from clearance.querysets import offered_scopes, visible
from clearance.rules import Rule
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Statement


def condition(field: str, operator: str, **value: Any) -> dict[str, Any]:
    return (
        {'field': field, 'operator': operator, 'value': value}
        if value
        else {
            'field': field,
            'operator': operator,
        }
    )


def stored_rule(
    model: type[Model], code: str, *conditions: dict[str, Any], match: str = 'all'
) -> ScopeRule:
    """A rule saved straight to the table, as an administrator's would be."""
    return ScopeRule.objects.create(
        content_type=ContentType.objects.get_for_model(model),
        code=code,
        name=code.replace('_', ' '),
        match=match,
        conditions=list(conditions),
    )


def reached(person: Person, model: type[Model], action: str = 'view') -> set[int]:
    fresh = Person.objects.get(pk=person.pk)
    return set(visible(model._default_manager.all(), fresh, action).values_list('pk', flat=True))


def pks(*rows: Model) -> set[int]:
    return {row.pk for row in rows}


@pytest.fixture
def north(make_user: MakeUser) -> Person:
    person = make_user()
    person.region = 'north'
    person.save()
    return person


@pytest.fixture
def loans(north: Person, make_user: MakeUser) -> dict[str, Loan]:
    return {
        'north_small': Loan.objects.create(applicant=north, amount=100, region='north'),
        'north_large': Loan.objects.create(applicant=make_user(), amount=900, region='north'),
        'south_large': Loan.objects.create(
            applicant=make_user(), amount=800, region='south', status='approved'
        ),
        'nowhere': Loan.objects.create(applicant=make_user(), amount=50, region=''),
    }


def give(person: Person, name: str, scope: str | None) -> None:
    person.user_permissions.add(permission(name))
    if scope is not None:
        ScopeGrant.objects.create(user=person, permission=permission(name), scope=scope)


# ---------------------------------------------------------------- what a rule reaches


def test_a_rule_on_a_constant_reaches_the_rows_it_describes(
    north: Person, loans: dict[str, Loan]
) -> None:
    stored_rule(Loan, 'large', condition('amount', 'at_least', constant=500))
    give(north, 'lending.loan_view', 'large')

    assert reached(north, Loan) == pks(loans['north_large'], loans['south_large'])


def test_a_rule_on_the_persons_own_field_follows_the_person(
    north: Person, loans: dict[str, Loan]
) -> None:
    stored_rule(Loan, 'their_region', condition('region', 'is', person='region'))
    give(north, 'lending.loan_view', 'their_region')

    assert reached(north, Loan) == pks(loans['north_small'], loans['north_large'])


def test_a_rule_on_the_person_reaches_their_own_rows(north: Person, loans: dict[str, Loan]) -> None:
    stored_rule(Loan, 'applied_for', condition('applicant', 'is', person=''))
    give(north, 'lending.loan_view', 'applied_for')

    assert reached(north, Loan) == pks(loans['north_small'])


def test_conditions_join_with_all_or_with_any(north: Person, loans: dict[str, Loan]) -> None:
    large = condition('amount', 'at_least', constant=500)
    northern = condition('region', 'is', constant='north')
    stored_rule(Loan, 'both', large, northern, match='all')
    stored_rule(Loan, 'either', large, northern, match='any')
    give(north, 'lending.loan_view', 'both')

    assert reached(north, Loan) == pks(loans['north_large'])

    ScopeGrant.objects.filter(user=north).update(scope='either')
    assert reached(north, Loan) == pks(
        loans['north_small'], loans['north_large'], loans['south_large']
    )


@pytest.mark.parametrize(
    ('conditions', 'expected'),
    [
        ([condition('region', 'is_not', constant='north')], {'south_large', 'nowhere'}),
        (
            [condition('region', 'is_one_of', constant=['north', 'south'])],
            {'north_small', 'north_large', 'south_large'},
        ),
        ([condition('region', 'contains', constant='OUT')], {'south_large'}),
        ([condition('region', 'is_empty')], {'nowhere'}),
        ([condition('amount', 'at_most', constant=100)], {'north_small', 'nowhere'}),
        ([condition('status', 'is', constant='approved')], {'south_large'}),
        ([condition('applicant__region', 'is', person='region')], {'north_small'}),
    ],
    ids=['is_not', 'is_one_of', 'contains', 'is_empty', 'at_most', 'a choice', 'across a relation'],
)
def test_each_operator_reaches_what_it_says(
    north: Person, loans: dict[str, Loan], conditions: list[dict[str, Any]], expected: set[str]
) -> None:
    stored_rule(Loan, 'chosen', *conditions)
    give(north, 'lending.loan_view', 'chosen')

    assert reached(north, Loan) == {loans[name].pk for name in expected}


def test_a_number_is_compared_with_the_persons_own(north: Person, loans: dict[str, Loan]) -> None:
    north.approval_limit = 100
    north.save()
    stored_rule(Loan, 'within_limit', condition('amount', 'at_most', person='approval_limit'))
    give(north, 'lending.loan_view', 'within_limit')

    assert reached(north, Loan) == pks(loans['north_small'], loans['nowhere'])


def test_a_yes_or_no_field_is_compared_with_yes_or_no(
    north: Person, loans: dict[str, Loan]
) -> None:
    Loan.objects.filter(pk=loans['north_large'].pk).update(approved=True)
    stored_rule(Loan, 'approved', condition('approved', 'is', constant=True))
    give(north, 'lending.loan_view', 'approved')

    assert reached(north, Loan) == pks(loans['north_large'])

    with pytest.raises(ValidationError, match='does not suit'):
        Rule.parse(Loan, 'all', [condition('approved', 'is_one_of', constant=[True])])


def test_a_field_of_a_kind_nothing_orders_is_only_matched_or_found_empty() -> None:
    assert rules.kind_of(UUIDField()) == rules.OTHER
    assert [
        code for code, operator in rules.OPERATORS.items() if rules.OTHER in operator.kinds
    ] == [
        'is',
        'is_not',
        'is_one_of',
        'is_empty',
    ]


def test_dates_are_compared_before_and_after(north: Person, loans: dict[str, Loan]) -> None:
    old = Statement.objects.create(
        loan=loans['north_small'], total=1, issued_on=datetime.date(2025, 1, 1)
    )
    new = Statement.objects.create(
        loan=loans['north_small'], total=1, issued_on=datetime.date(2026, 6, 1)
    )
    stored_rule(Statement, 'this_year', condition('issued_on', 'after', constant='2026-01-01'))
    stored_rule(Statement, 'earlier', condition('issued_on', 'before', constant='2026-01-01'))
    give(north, 'lending.view_statement', 'this_year')

    assert reached(north, Statement) == pks(new)

    ScopeGrant.objects.filter(user=north).update(scope='earlier')
    assert reached(north, Statement) == pks(old)


# ---------------------------------------------------------------- any model


def test_a_model_with_no_access_code_is_scoped_by_its_rules(
    north: Person, loans: dict[str, Loan], make_bundle: MakeBundle
) -> None:
    mine = Statement.objects.create(loan=loans['north_small'], region='north', total=1)
    Statement.objects.create(loan=loans['south_large'], region='south', total=1)
    stored_rule(Statement, 'their_region', condition('region', 'is', person='region'))
    north.groups.add(make_bundle({'lending.view_statement': 'their_region'}))

    assert reached(north, Statement) == pks(mine)


def test_on_a_model_with_no_access_code_a_grant_with_no_scope_reaches_every_row(
    north: Person, loans: dict[str, Loan]
) -> None:
    both = [Statement.objects.create(loan=loan, total=1) for loan in loans.values()]
    give(north, 'lending.view_statement', None)

    assert reached(north, Statement) == pks(*both), 'as Django has always done'


def test_a_rule_scope_joins_a_code_scope_in_their_union(
    north: Person, loans: dict[str, Loan], make_bundle: MakeBundle
) -> None:
    stored_rule(Loan, 'large', condition('amount', 'at_least', constant=850))
    north.groups.add(
        make_bundle({'lending.loan_view': 'own'}), make_bundle({'lending.loan_view': 'large'})
    )

    assert reached(north, Loan) == pks(loans['north_small'], loans['north_large'])


@pytest.mark.django_db
def test_rule_scopes_are_offered_beside_the_code_scopes() -> None:
    stored_rule(Loan, 'large', condition('amount', 'at_least', constant=500))

    assert list(offered_scopes(Loan)) == ['all', 'own', 'reviewing', 'large']
    assert list(offered_scopes(Statement)) == ['all']


# ---------------------------------------------------------------- what is refused


@pytest.mark.parametrize(
    ('raw', 'message'),
    [
        ([], 'at least one condition'),
        ([condition('colour', 'is', constant='red')], 'Loan has no field'),
        ([condition('amount', 'contains', constant='1')], 'does not suit'),
        ([condition('amount', 'is', constant='lots')], 'is not a value'),
        ([condition('status', 'is', constant='lost')], 'is not one of the choices'),
        ([condition('applicant__password', 'is', constant='x')], 'may not be read'),
        ([condition('region', 'is', person='password')], 'may not be read'),
        ([condition('amount', 'is', person='region')], 'holds number'),
        ([condition('applicant', 'is', person='region')], 'reaches Person'),
        ([condition('region', 'sounds_like', constant='north')], 'is not an operator'),
        ([condition('region', 'is', constant='north', person='region')], 'The value is'),
        ([condition('region', 'is_one_of', constant='north')], 'takes a list'),
        ([{'operator': 'is'}], 'names a field'),
        (['region is north'], 'a field, an operator and a value'),
        ([condition('region__name', 'is', constant='north')], "'region' leads nowhere"),
    ],
)
def test_a_rule_that_cannot_work_is_refused_when_it_is_saved(raw: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Rule.parse(Loan, 'all', raw)


def test_a_match_other_than_all_or_any_is_refused() -> None:
    with pytest.raises(ValidationError, match='match must be one of'):
        Rule.parse(Loan, 'most', [condition('region', 'is', constant='north')])


def test_a_rule_reaches_at_most_as_far_as_the_setting_allows() -> None:
    far = [condition('loan__applicant__region', 'is', constant='north')]
    Rule.parse(Statement, 'all', far)

    with (
        override_settings(CLEARANCE={'RULE_DEPTH': 1}),
        pytest.raises(ValidationError, match='more than 1 relations'),
    ):
        Rule.parse(Statement, 'all', far)


def test_a_field_the_protected_fields_guard_may_not_be_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rules, 'unreadable_checks', [lambda model, name: name == 'amount'])

    with pytest.raises(ValidationError, match=r'Loan\.amount may not be read'):
        Rule.parse(Loan, 'all', [condition('amount', 'at_least', constant=1)])


def test_a_rule_whose_field_is_gone_reaches_nothing_and_says_so(
    north: Person, loans: dict[str, Loan], caplog: pytest.LogCaptureFixture
) -> None:
    stored_rule(Loan, 'broken', condition('vanished', 'is', constant='x'))
    give(north, 'lending.loan_view', 'broken')

    with caplog.at_level(logging.WARNING, logger='clearance'):
        assert reached(north, Loan) == set()

    assert "Scope rule 'broken' of lending.Loan reaches nothing" in caplog.text


@pytest.mark.django_db
def test_a_rule_whose_model_is_gone_cannot_be_checked() -> None:
    gone = ContentType.objects.create(app_label='lending', model='overdraft')
    rule = ScopeRule.objects.create(
        content_type=gone, code='any', name='Any', conditions=[condition('x', 'is_empty')]
    )

    with pytest.raises(ValidationError, match='no longer exists'):
        rule.compiled()


# ---------------------------------------------------------------- what it costs


def test_rules_are_read_once_per_person_and_model(
    north: Person, loans: dict[str, Loan], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    stored_rule(Loan, 'large', condition('amount', 'at_least', constant=500))
    give(north, 'lending.loan_view', 'large')
    person = Person.objects.get(pk=north.pk)

    with django_assert_num_queries(3):  # their grants, the model's rules, the list
        list(visible(Loan.objects.all(), person))

    with django_assert_num_queries(1):
        list(visible(Loan.objects.all(), person))


# ---------------------------------------------------------------- managing rules


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    return make_user(
        'clearance.permission_create',
        'clearance.permission_edit',
        'clearance.permission_delete',
        ('lending.loan_view', 'all'),
    )


@pytest.fixture
def access(manager: Person, make_user: MakeUser) -> AccessService:
    make_user('clearance.permission_edit')  # somebody else who manages access
    return AccessService(actor=manager)


def test_a_rule_is_made_through_the_service_and_can_then_be_granted(
    access: AccessService, make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    access.create_scope_rule(
        Loan, 'large', 'Large loans', [condition('amount', 'at_least', constant=500)]
    )
    person = make_user()
    access.grant(person, 'lending.loan_view', 'large')

    assert reached(person, Loan) == pks(loans['north_large'], loans['south_large'])


@pytest.mark.parametrize(
    ('code', 'message'),
    [('all', 'already a scope'), ('own', 'already a scope'), ('two words', 'is not a code')],
)
def test_a_rule_may_not_take_a_code_already_taken_or_not_a_code(
    access: AccessService, code: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        access.create_scope_rule(
            Loan, code, 'Anything', [condition('amount', 'at_least', constant=1)]
        )


def test_making_rules_needs_the_permission_to_manage_access(make_user: MakeUser) -> None:
    with pytest.raises(AccessRefused):
        AccessService(actor=make_user()).create_scope_rule(
            Loan, 'large', 'Large', [condition('amount', 'at_least', constant=1)]
        )


def test_nobody_changes_the_rows_of_a_scope_their_own_grants_are_in(
    access: AccessService, manager: Person
) -> None:
    rule = access.create_scope_rule(
        Loan, 'large', 'Large', [condition('amount', 'at_least', constant=500)]
    )
    ScopeGrant.objects.filter(user=manager, permission=permission('lending.loan_view')).update(
        scope='large'
    )

    with pytest.raises(AccessRefused) as refused:
        access.change_scope_rule(rule, conditions=[condition('amount', 'at_least', constant=1)])

    assert refused.value.rule == 'own_scope'
    access.change_scope_rule(rule, name='Big loans')  # renaming reaches no new rows
    assert ScopeRule.objects.get(pk=rule.pk).name == 'Big loans'


def test_a_rule_that_cannot_work_is_not_saved_through_the_service(
    access: AccessService,
) -> None:
    with pytest.raises(ValidationError, match='Loan has no field'):
        access.create_scope_rule(Loan, 'odd', 'Odd', [condition('colour', 'is', constant='red')])

    assert not ScopeRule.objects.exists()


def test_the_superuser_changes_a_rule_their_grants_are_in(make_user: MakeUser) -> None:
    superuser = make_user(('lending.loan_view', 'all'), superuser=True)
    access = AccessService(actor=superuser)
    rule = access.create_scope_rule(
        Loan, 'large', 'Large', [condition('amount', 'at_least', constant=1)]
    )
    ScopeGrant.objects.filter(user=superuser).update(scope='large')

    access.change_scope_rule(rule, match='any')

    assert ScopeRule.objects.get(pk=rule.pk).match == 'any'


def test_a_rule_still_chosen_in_a_grant_is_not_deleted(
    access: AccessService, make_user: MakeUser
) -> None:
    rule = access.create_scope_rule(
        Loan, 'large', 'Large', [condition('amount', 'at_least', constant=500)]
    )
    access.grant(make_user(), 'lending.loan_view', 'large')

    with pytest.raises(ValidationError, match='is the scope of 1 grant'):
        access.delete_scope_rule(rule)


def test_saving_and_deleting_a_rule_is_announced(
    access: AccessService, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    caught: list[tuple[Signal, dict[str, Any]]] = []

    def receiver(signal: Signal, **kwargs: Any) -> None:
        caught.append((signal, kwargs))

    signals.scope_rule_saved.connect(receiver, weak=False)
    signals.scope_rule_deleted.connect(receiver, weak=False)

    try:
        with django_capture_on_commit_callbacks(execute=True):
            rule = access.create_scope_rule(
                Loan, 'large', 'Large', [condition('amount', 'at_least', constant=1)]
            )
            access.change_scope_rule(rule, match='any')
            access.delete_scope_rule(rule)
    finally:
        signals.scope_rule_saved.disconnect(receiver)
        signals.scope_rule_deleted.disconnect(receiver)

    assert [(signal, kwargs.get('created', kwargs.get('code'))) for signal, kwargs in caught] == [
        (signals.scope_rule_saved, True),
        (signals.scope_rule_saved, False),
        (signals.scope_rule_deleted, 'large'),
    ]


@pytest.mark.django_db
def test_a_rule_says_what_it_is() -> None:
    rule = stored_rule(Loan, 'large', condition('amount', 'at_least', constant=1))

    assert str(rule) == 'loan: large'
