"""
The admin site builds rule scopes, protects fields and makes status actions -
each page writing through the service, under the same rules as the code.

If these fail, a rule built on its page reaches rows its conditions do not
describe, a page lets somebody protect a field a rule reads or unprotect one
they were never given, or a status action claims values nobody chose.
"""

from typing import Any

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client

from clearance.admin.scopes import conditions_from, field_paths
from clearance.models import Declared, ProtectedField, ScopeGrant, ScopeRule, StatusAction
from clearance.services import AccessService
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

MANAGER = (
    'clearance.permission_view',
    'clearance.permission_create',
    'clearance.permission_edit',
    'clearance.permission_delete',
)


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    make_user('clearance.permission_edit')  # somebody else who manages access
    person = make_user(*MANAGER, ('lending.loan_view', 'all'))
    person.is_staff = True
    person.save()
    return Person.objects.get(pk=person.pk)


@pytest.fixture
def signed_in(client: Client, manager: Person) -> Client:
    client.force_login(manager)
    return client


def notices(response: Any) -> list[str]:
    return [str(message) for message in response.context['messages']]


def loan_rule(code: str = 'large', **extra: Any) -> ScopeRule:
    return ScopeRule.objects.create(
        content_type=ContentType.objects.get_for_model(Loan),
        code=code,
        name=code.title(),
        conditions=[{'field': 'amount', 'operator': 'at_least', 'value': {'constant': 500}}],
        **extra,
    )


# ---------------------------------------------------------------- looking


@pytest.mark.parametrize(
    'address',
    ['/admin/access/scopes/', '/admin/access/fields/', '/admin/access/actions/'],
)
def test_the_pages_need_the_permission_to_view_access(
    client: Client, make_user: MakeUser, address: str
) -> None:
    staff = make_user()
    staff.is_staff = True
    staff.save()
    client.force_login(staff)

    assert client.get(address).status_code == 403


def test_the_index_offers_every_page(signed_in: Client) -> None:
    html = signed_in.get('/admin/').content.decode()

    for address in ('/admin/access/scopes/', '/admin/access/fields/', '/admin/access/actions/'):
        assert address in html


def test_the_overview_says_what_the_database_holds_wrong(signed_in: Client) -> None:
    Permission.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), codename='loan_fly', name='Can fly'
    )

    assert (
        'lending.loan_fly is checked by nothing' in signed_in.get('/admin/access/').content.decode()
    )


# ---------------------------------------------------------------- row scopes


def test_every_scope_is_listed_with_the_grants_using_it(signed_in: Client) -> None:
    rule = loan_rule()
    ScopeGrant.objects.filter(scope='all').update(scope='large')

    rows = {
        (row['model'], row['code']): row
        for row in signed_in.get('/admin/access/scopes/').context['rows']
    }

    assert rows[('lending.Loan', 'own')]['rule'] is None
    assert rows[('lending.Loan', 'large')]['rule'] == rule
    assert rows[('lending.Loan', 'large')]['grants'] == 1


def test_a_rule_that_reaches_nothing_is_marked(signed_in: Client) -> None:
    loan_rule()
    ProtectedField.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), field='amount'
    )

    (rule,) = [row for row in signed_in.get('/admin/access/scopes/').context['rows'] if row['rule']]
    assert rule['broken']


def test_the_builder_offers_the_fields_a_rule_may_read(signed_in: Client) -> None:
    response = signed_in.get('/admin/access/scopes/add/', {'model': 'lending.Loan'})
    paths = response.context['paths']

    assert {'amount', 'region', 'applicant__region', 'applicant'} <= set(paths)
    assert 'credit_score' not in paths, 'protected'
    assert 'applicant__password' not in paths
    assert signed_in.get('/admin/access/scopes/add/', {'model': 'lending.Ghost'}).status_code == 404


def test_a_rule_is_built_from_its_page(signed_in: Client) -> None:
    response = signed_in.post(
        '/admin/access/scopes/add/?model=lending.Loan',
        {
            'code': 'northern',
            'name': 'Northern',
            'match': 'any',
            'field': ['region', 'status', 'officer', 'applicant', ''],
            'operator': ['is', 'is_one_of', 'is_empty', 'is', 'is'],
            'kind': ['person', 'constant', 'constant', 'person', 'constant'],
            'value': ['region', 'pending, approved', '', '', 'left empty'],
        },
        follow=True,
    )

    rule = ScopeRule.objects.get(code='northern')
    assert notices(response) == ['The rule scope was saved.']
    assert rule.match == 'any'
    assert rule.conditions == [
        {'field': 'region', 'operator': 'is', 'value': {'person': 'region'}},
        {
            'field': 'status',
            'operator': 'is_one_of',
            'value': {'constant': ['pending', 'approved']},
        },
        {'field': 'officer', 'operator': 'is_empty'},
        {'field': 'applicant', 'operator': 'is', 'value': {'person': ''}},
    ]


def test_a_rule_that_cannot_work_is_refused_naming_its_condition(signed_in: Client) -> None:
    response = signed_in.post(
        '/admin/access/scopes/add/?model=lending.Loan',
        {
            'code': 'odd',
            'name': 'Odd',
            'match': 'all',
            'field': ['colour'],
            'operator': ['is'],
            'kind': ['constant'],
            'value': ['red'],
        },
    )

    assert any(
        'Condition 1' in error and 'no field' in error for error in response.context['errors']
    )
    assert not ScopeRule.objects.exists()


def test_a_rule_is_shown_and_changed_on_its_page(signed_in: Client) -> None:
    rule = loan_rule()
    rule.conditions = [
        {'field': 'region', 'operator': 'is_one_of', 'value': {'constant': ['north', 'south']}},
        {'field': 'applicant', 'operator': 'is', 'value': {'person': ''}},
    ]
    rule.save()
    address = f'/admin/access/scopes/{rule.pk}/'

    rows = signed_in.get(address).context['rows']
    assert rows[0] == {
        'field': 'region',
        'operator': 'is_one_of',
        'kind': 'constant',
        'value': 'north, south',
    }
    assert rows[1]['kind'] == 'person'

    signed_in.post(
        address,
        {
            'code': 'large',
            'name': 'Big',
            'match': 'all',
            'field': ['amount'],
            'operator': ['at_most'],
            'kind': ['constant'],
            'value': ['10'],
        },
    )
    rule.refresh_from_db()
    assert (rule.name, rule.conditions[0]['operator']) == ('Big', 'at_most')


def test_nobody_changes_on_its_page_a_rule_their_grants_are_in(
    signed_in: Client, manager: Person
) -> None:
    rule = loan_rule()
    ScopeGrant.objects.filter(user=manager, scope='all').update(scope='large')

    response = signed_in.post(
        f'/admin/access/scopes/{rule.pk}/',
        {
            'code': 'large',
            'name': 'Large',
            'match': 'all',
            'field': ['amount'],
            'operator': ['at_least'],
            'kind': ['constant'],
            'value': ['1'],
        },
    )

    assert response.context['errors'] == [
        'Nobody changes the rows of a scope their own grants are in.'
    ]


def test_a_rule_still_chosen_is_not_deleted_and_one_unused_is(
    signed_in: Client, make_user: MakeUser
) -> None:
    rule = loan_rule()
    AccessService(actor=None).grant(make_user(), 'lending.loan_view', 'large')
    address = f'/admin/access/scopes/{rule.pk}/delete/'

    assert 'choose another for it first' in signed_in.get(address).content.decode()
    assert any(
        'is the scope of 1 grant' in n for n in notices(signed_in.post(address, follow=True))
    )

    ScopeGrant.objects.filter(scope='large').delete()
    assert 'No grant chooses this scope' in signed_in.get(address).content.decode()
    assert notices(signed_in.post(address, follow=True)) == ['The rule scope was deleted.']
    assert not ScopeRule.objects.exists()


def test_a_submitted_condition_row_with_no_field_is_a_row_left_empty() -> None:
    from django.http import QueryDict

    data = QueryDict(mutable=True)
    data.setlist('field', ['', 'region'])
    data.setlist('operator', ['is', 'contains'])
    data.setlist('kind', ['constant', 'constant'])
    data.setlist('value', ['x', 'nor'])

    assert list(conditions_from(data)) == [
        {'field': 'region', 'operator': 'contains', 'value': {'constant': 'nor'}}
    ]


def test_the_paths_reach_one_relation_and_no_protected_field() -> None:
    paths = list(field_paths(Payment))

    assert 'loan__amount' in paths
    assert 'loan__credit_score' not in paths
    assert not any(path.count('__') > 1 for path in paths)


# ---------------------------------------------------------------- protected fields


def test_every_model_is_listed_with_how_many_fields_it_protects(signed_in: Client) -> None:
    rows = {
        label: count for label, _, count in signed_in.get('/admin/access/fields/').context['rows']
    }

    assert rows['lending.Loan'] == 1
    assert rows['lending.Payment'] == 0


def test_a_models_page_says_how_each_field_is_protected(signed_in: Client) -> None:
    fields = {
        field['name']: field
        for field in signed_in.get('/admin/access/fields/lending.Loan/').context['fields']
    }

    assert fields['credit_score']['in_code']
    assert fields['credit_score']['permissions']['view'] == 'lending.loan_view_credit_score'
    assert 'primary key' in fields['id']['cannot']
    assert not fields['amount']['protected']


def test_a_field_is_protected_and_unprotected_from_its_page(
    signed_in: Client, manager: Person
) -> None:
    address = '/admin/access/fields/lending.Payment/'

    assert notices(signed_in.post(address, {'do': 'protect', 'field': 'amount'}, follow=True)) == [
        'amount is protected.'
    ]
    assert ProtectedField.objects.filter(field='amount').exists()

    refused = signed_in.post(address, {'do': 'unprotect', 'field': 'amount'}, follow=True)
    assert any('do not hold' in notice for notice in notices(refused)), 'never given it'

    AccessService(actor=None).grant(manager, 'lending.view_payment_amount')
    AccessService(actor=None).grant(manager, 'lending.change_payment_amount')
    assert notices(
        signed_in.post(address, {'do': 'unprotect', 'field': 'amount'}, follow=True)
    ) == ['amount is no longer protected.']


# ---------------------------------------------------------------- actions


def test_the_actions_page_lists_every_kind(signed_in: Client) -> None:
    AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded']
    )
    Permission.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), codename='loan_fly', name='Can fly'
    )

    context = signed_in.get('/admin/access/actions/').context

    assert [row.code for row, _ in context['made']] == ['refund']
    assert ('lending.Loan', 'approve') in [(label, code) for label, code, _ in context['in_code']]
    assert 'lending.loan_export' in {action.permission for action in context['found']}
    assert ['lending.loan_fly' in finding.message for finding in context['gone']] == [True]


def test_a_status_action_is_made_in_two_steps(signed_in: Client) -> None:
    first = signed_in.get('/admin/access/actions/add/', {'model': 'lending.Payment'})
    assert first.context['fields'] == ['state']

    second = signed_in.get(
        '/admin/access/actions/add/', {'model': 'lending.Payment', 'field': 'state'}
    )
    assert [value for value, _ in second.context['values']] == ['due', 'paid', 'refunded']

    signed_in.post(
        '/admin/access/actions/add/?model=lending.Payment&field=state',
        {'code': 'refund', 'name': 'Refund', 'to': ['refunded'], 'from': ['paid']},
    )
    action = StatusAction.objects.get()
    assert (action.code, action.to_values, action.from_values) == ('refund', ['refunded'], ['paid'])


def test_a_status_action_that_cannot_work_says_why(signed_in: Client) -> None:
    response = signed_in.post(
        '/admin/access/actions/add/?model=lending.Payment&field=state', {'code': 'Refund!'}
    )

    assert any('is not an action' in error for error in response.context['errors'])
    assert (
        signed_in.get(
            '/admin/access/actions/add/', {'model': 'lending.Payment', 'field': 'nonsense'}
        ).context['values']
        == []
    )


def test_a_status_action_is_changed_and_deleted_from_its_page(
    signed_in: Client, manager: Person
) -> None:
    action = AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded']
    )
    AccessService(actor=None).grant(manager, 'lending.payment_refund', 'all')  # to delete it
    address = f'/admin/access/actions/{action.pk}/'

    page = signed_in.get(address).context
    assert (page['to'], page['claimed_elsewhere']) == ({'refunded'}, [])

    signed_in.post(address, {'name': 'Give back', 'to': ['refunded'], 'from': ['paid']})
    action.refresh_from_db()
    assert (action.name, action.from_values) == ('Give back', ['paid'])

    assert 'takes its permission' in signed_in.get(f'{address}delete/').content.decode()
    assert notices(signed_in.post(f'{address}delete/', follow=True)) == [
        'The status action was deleted.'
    ]


def test_a_status_action_the_rules_keep_is_kept(signed_in: Client, make_user: MakeUser) -> None:
    action = AccessService(actor=None).create_status_action(
        Payment, 'void', 'Void', 'state', ['refunded']
    )
    AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded']
    )
    address = f'/admin/access/actions/{action.pk}/'

    assert signed_in.get(address).context['claimed_elsewhere'] == ['refund: refunded']
    refused = signed_in.post(f'{address}delete/', follow=True)
    assert any('do not hold' in notice for notice in notices(refused))
    assert StatusAction.objects.filter(pk=action.pk).exists()


def test_a_status_action_the_file_declares_is_read_only_on_its_page(signed_in: Client) -> None:
    action = AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded']
    )
    Declared.objects.create(kind='status_action', key='lending.Payment.refund')

    html = signed_in.get(f'/admin/access/actions/{action.pk}/').content.decode()
    assert 'Declared in code' in html
    assert 'value="Save"' not in html
    assert 'in the ACCESS file' in signed_in.get('/admin/access/actions/').content.decode()


def test_the_first_step_of_a_status_action_carries_its_model_to_the_second(
    signed_in: Client,
) -> None:
    html = signed_in.get(
        '/admin/access/actions/add/', {'model': 'lending.Payment'}
    ).content.decode()

    assert '<input type="hidden" name="model" value="lending.Payment">' in html
    assert '<code>lending.Payment</code>' in html


def test_the_rule_builder_names_its_model(signed_in: Client) -> None:
    html = signed_in.get('/admin/access/scopes/add/', {'model': 'lending.Loan'}).content.decode()

    assert '<code>lending.Loan</code>' in html
