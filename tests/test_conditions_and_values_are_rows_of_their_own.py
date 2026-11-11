"""
A rule's conditions and a status action's values are rows of their own - no
JSON column - written with the row they belong to, read back in words, and
moved out of the columns that held them before.

If these fail, saving a rule loses its conditions or keeps the old ones beside
the new, a status action forgets where it writes from, reading the rules of a
list costs a query per rule, or a database that held rules before this
release migrates to rules that reach nothing.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from pytest_django import DjangoAssertNumQueries

from clearance.models import (
    ScopeCondition,
    ScopeConditionValue,
    ScopeRule,
    StatusAction,
    StatusActionValue,
)
from tests.project.lending.models import Loan

pytestmark = pytest.mark.django_db

AMOUNT = {'field': 'amount', 'operator': 'at_least', 'value': {'constant': 500}}
REGION = {'field': 'region', 'operator': 'is', 'value': {'person': 'region'}}
STATUS = {'field': 'status', 'operator': 'is_one_of', 'value': {'constant': ['pending', 'paid']}}
EMPTY = {'field': 'region', 'operator': 'is_empty'}


def a_rule(*conditions: dict[str, Any], code: str = 'large') -> ScopeRule:
    return ScopeRule.objects.create(
        content_type=ContentType.objects.get_for_model(Loan),
        code=code,
        name=code.title(),
        conditions=list(conditions),
    )


def an_action(**values: list[Any]) -> StatusAction:
    action = StatusAction(
        content_type=ContentType.objects.get_for_model(Loan),
        code='close',
        name='Close',
        field='status',
    )
    action.to_values = values.get('to', ['closed'])
    action.from_values = values.get('start', [])
    action.save()
    return action


# ---------------------------------------------------------------- a rule's conditions


def test_a_rules_conditions_are_rows_read_back_in_words() -> None:
    rule = a_rule(AMOUNT, REGION, STATUS, EMPTY)

    assert ScopeCondition.objects.filter(rule=rule).count() == 4
    assert list(
        ScopeConditionValue.objects.filter(condition__rule=rule).values_list('value', flat=True)
    ) == ['500', 'pending', 'paid']
    assert ScopeRule.objects.get(pk=rule.pk).conditions == [
        {**AMOUNT, 'value': {'constant': '500'}},
        REGION,
        STATUS,
        EMPTY,
    ]


def test_conditions_set_replace_the_ones_a_rule_had_when_it_is_saved() -> None:
    rule = a_rule(AMOUNT, STATUS)
    rule.conditions = [EMPTY]

    assert ScopeRule.objects.get(pk=rule.pk).conditions != [EMPTY], 'not before it is saved'
    rule.save()

    assert ScopeRule.objects.get(pk=rule.pk).conditions == [EMPTY]
    assert not ScopeConditionValue.objects.exists()


def test_saving_a_rule_without_setting_conditions_keeps_them() -> None:
    rule = a_rule(AMOUNT)
    rule = ScopeRule.objects.get(pk=rule.pk)
    rule.name = 'Big'
    rule.save()

    assert ScopeRule.objects.get(pk=rule.pk).conditions == [
        {**AMOUNT, 'value': {'constant': '500'}}
    ]


def test_a_rule_not_yet_saved_has_the_conditions_set_or_none() -> None:
    assert ScopeRule().conditions == []
    assert ScopeRule(conditions=[AMOUNT]).conditions == [AMOUNT]


def test_no_value_is_kept_as_no_value() -> None:
    rule = a_rule({'field': 'region', 'operator': 'is', 'value': {'constant': None}})

    assert ScopeRule.objects.get(pk=rule.pk).conditions[0]['value'] == {'constant': ''}
    assert ScopeRule.stored_form([{'field': 'x', 'operator': 'is'}, 'nonsense']) == [  # type: ignore[list-item]
        {'field': 'x', 'operator': 'is'},
        {'field': '', 'operator': ''},
    ]


def test_the_rules_of_a_list_are_read_in_a_fixed_number_of_queries(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    for number in range(3):
        a_rule(AMOUNT, STATUS, REGION, code=f'rule_{number}')

    with django_assert_num_queries(3):
        rules = list(ScopeRule.objects.with_conditions())
        assert all(len(rule.conditions) == 3 for rule in rules)

    with django_assert_num_queries(1):
        read = ScopeRule.objects.read()

    assert [code for code, _, _ in read] == ['rule_0', 'rule_1', 'rule_2']
    assert read[0][2][1] == STATUS


# ---------------------------------------------------------------- a status action's values


def test_a_status_actions_values_are_rows_read_back_in_words() -> None:
    action = an_action(to=['closed', 'closed', 'declined'], start=['pending'])
    found = StatusAction.objects.with_values().get(pk=action.pk)

    assert (found.to_values, found.from_values) == (['closed', 'declined'], ['pending'])
    assert StatusActionValue.objects.filter(action=action).count() == 3


def test_values_set_are_read_before_they_are_saved_and_kept_when_not_set() -> None:
    action = an_action(to=['closed'], start=['pending'])
    action.to_values = ['declined']

    assert action.to_values == ['declined']
    assert action.from_values == ['pending'], 'read from its rows'
    action.save()
    action = StatusAction.objects.get(pk=action.pk)
    action.name = 'Shut'
    action.save()

    assert (action.to_values, action.from_values) == (['declined'], ['pending'])
    assert StatusAction().to_values == []


def test_each_row_says_what_it_is() -> None:
    a_rule(STATUS)
    an_action(to=['closed'])

    assert str(ScopeCondition.objects.get()) == 'status is_one_of'
    assert str(ScopeConditionValue.objects.first()) == 'pending'
    assert str(StatusActionValue.objects.get()) == 'to closed'


# ---------------------------------------------------------------- the migration


@pytest.fixture
def before_the_rows() -> Iterator[Any]:
    """The database as it was with JSON columns - and back to now afterwards."""
    executor = MigrationExecutor(connection)
    executor.migrate([('clearance', '0005_declared')])
    executor.loader.build_graph()
    yield executor.loader.project_state(('clearance', '0005_declared')).apps
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_what_the_json_columns_held_moves_into_rows(before_the_rows: Any) -> None:
    old_rule = before_the_rows.get_model('clearance', 'ScopeRule')
    old_action = before_the_rows.get_model('clearance', 'StatusAction')
    content_type = before_the_rows.get_model('contenttypes', 'ContentType').objects.get(
        app_label='lending', model='loan'
    )
    old_rule.objects.create(
        content_type=content_type,
        code='large',
        name='Large',
        conditions=[AMOUNT, REGION, STATUS, EMPTY, 'nonsense', {'value': {'constant': None}}],
    )
    old_action.objects.create(
        content_type=content_type,
        code='close',
        name='Close',
        field='status',
        to_values=['closed', 'closed'],
        from_values=['pending'],
    )

    executor = MigrationExecutor(connection)
    executor.migrate([('clearance', '0006_rows_not_json')])

    assert ScopeRule.objects.get().conditions == [
        {**AMOUNT, 'value': {'constant': '500'}},
        REGION,
        STATUS,
        EMPTY,
        {'field': '', 'operator': ''},
        {'field': '', 'operator': '', 'value': {'constant': ''}},
    ]
    action = StatusAction.objects.get()
    assert (action.to_values, action.from_values) == (['closed'], ['pending'])
