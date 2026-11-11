"""
The access pages of the admin site show who holds what, and change it only
through the service, under the same safety rules as the code.

If these fail, the admin site is a way round the rules: somebody who may only
look at access changes it, an administrator gives themselves a bundle or a
permission they never held, the grid saves a scope nobody chose, or a page
shows somebody allowed what they are not.
"""

from typing import Any

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.test import Client, RequestFactory
from pytest_django import DjangoAssertNumQueries

from clearance.admin.standing import PermissionGrid, Standing
from clearance.models import ScopeGrant, ScopeRule
from clearance.services import AccessService
from tests.conftest import MakeBundle, MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan

pytestmark = pytest.mark.django_db

MANAGER = (
    'clearance.permission_view',
    'clearance.permission_create',
    'clearance.permission_edit',
    'clearance.permission_delete',
)


@pytest.fixture
def make_staff(make_user: MakeUser) -> Any:
    def make(*permissions: Any, bundles: Any = (), superuser: bool = False) -> Person:
        person = make_user(*permissions, bundles=bundles, superuser=superuser)
        person.is_staff = True
        person.save()
        return Person.objects.get(pk=person.pk)

    return make


@pytest.fixture
def manager(make_staff: Any, make_user: MakeUser) -> Person:
    make_user('clearance.permission_edit')  # somebody else who manages access
    return make_staff(*MANAGER, ('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))


def signed_in(client: Client, person: Person) -> Client:
    client.force_login(person)
    return client


def shown(response: Any) -> str:
    return response.content.decode()


def notices(response: Any) -> list[str]:
    return [str(message) for message in response.context['messages']]


# ---------------------------------------------------------------- looking


@pytest.mark.parametrize(
    'address',
    [
        '/admin/access/',
        '/admin/access/bundles/',
        '/admin/access/people/',
        '/admin/access/permissions/',
    ],
)
def test_looking_needs_the_permission_to_view_access(
    client: Client, make_staff: Any, address: str
) -> None:
    assert signed_in(client, make_staff()).get(address).status_code == 403
    assert (
        signed_in(client, make_staff('clearance.permission_view')).get(address).status_code == 200
    )


def test_the_admin_index_offers_the_pages_to_whoever_may_look(
    client: Client, make_staff: Any
) -> None:
    viewer = shown(signed_in(client, make_staff('clearance.permission_view')).get('/admin/'))
    assert '/admin/access/bundles/' in viewer
    assert '/admin/access/bundles/add/' not in viewer, 'they may not make one'

    creator = make_staff('clearance.permission_view', 'clearance.permission_create')
    assert '/admin/access/bundles/add/' in shown(signed_in(client, creator).get('/admin/'))
    assert '/admin/access/' not in shown(
        signed_in(client, make_staff('lending.loan_view')).get('/admin/')
    )


def test_the_overview_counts_what_there_is(
    client: Client, manager: Person, make_bundle: MakeBundle
) -> None:
    make_bundle({'lending.loan_view': 'all'}, name='Readers')
    response = signed_in(client, manager).get('/admin/access/')

    assert response.context['bundles'] == 1
    assert response.context['people'] >= 2
    assert 0 < response.context['unheld'] < response.context['permissions']


# ---------------------------------------------------------------- bundles


def grid_post(name: str, grants: dict[str, str | None]) -> dict[str, Any]:
    return {
        'name': name,
        'grant': list(grants),
        **{f'scope:{permission}': scope or '' for permission, scope in grants.items()},
    }


def test_a_bundle_is_made_from_the_grid_with_a_scope_beside_each_tick(
    client: Client, manager: Person
) -> None:
    response = signed_in(client, manager).post(
        '/admin/access/bundles/add/',
        grid_post('Loan clerks', {'lending.loan_view': 'all', 'lending.loan_edit': None}),
    )

    bundle = Group.objects.get(name='Loan clerks')
    assert response.status_code == 302
    assert AccessService(actor=None).bundle_grants(bundle) == {
        'lending.loan_view': 'all',
        'lending.loan_edit': None,
    }


def test_the_grid_shows_a_bundle_as_it_stands(
    client: Client, manager: Person, make_bundle: MakeBundle
) -> None:
    bundle = make_bundle({'lending.loan_view': 'own'}, name='Customers')
    html = shown(signed_in(client, manager).get(f'/admin/access/bundles/{bundle.pk}/'))

    assert 'value="lending.loan_view" checked' in html
    assert '<option value="own" selected>' in html


def test_a_bundle_is_changed_and_renamed_from_the_grid(
    client: Client, manager: Person, make_bundle: MakeBundle
) -> None:
    bundle = make_bundle({'lending.loan_view': 'own'}, name='Customers')

    signed_in(client, manager).post(
        f'/admin/access/bundles/{bundle.pk}/',
        grid_post('Clients', {'lending.loan_view': 'all'}),
    )

    bundle.refresh_from_db()
    assert bundle.name == 'Clients'
    assert AccessService(actor=None).bundle_grants(bundle) == {'lending.loan_view': 'all'}


@pytest.mark.parametrize(
    ('name', 'grants', 'error'),
    [
        ('', {}, 'A bundle needs a name.'),
        ('Taken', {}, 'There is a bundle called Taken already.'),
        ('Thieves', {'lending.loan_delete': 'all'}, 'You cannot give a permission you do not hold'),
        ('Wrong', {'lending.loan_view': 'everywhere'}, 'its model offers no scope'),
    ],
)
def test_a_bundle_that_cannot_be_saved_says_why(
    client: Client,
    manager: Person,
    make_bundle: MakeBundle,
    name: str,
    grants: dict[str, str | None],
    error: str,
) -> None:
    make_bundle({}, name='Taken')
    response = signed_in(client, manager).post(
        '/admin/access/bundles/add/', grid_post(name, grants)
    )

    assert response.status_code == 200
    assert any(error in message for message in response.context['errors'])
    assert not Group.objects.filter(name__in=['Thieves', 'Wrong']).exists()


def test_somebody_who_may_only_look_cannot_save_a_bundle(client: Client, make_staff: Any) -> None:
    viewer = make_staff('clearance.permission_view')
    response = signed_in(client, viewer).post('/admin/access/bundles/add/', grid_post('Mine', {}))

    assert 'You may not create access.' in response.context['errors']
    assert 'value="Save"' not in shown(response), 'nothing to save with'


def test_a_bundle_is_deleted_after_saying_whom_it_reaches(
    client: Client, manager: Person, make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    bundle = make_bundle({'lending.loan_view': 'all'}, name='Readers')
    holder = make_user(bundles=(bundle,))
    address = f'/admin/access/bundles/{bundle.pk}/delete/'

    assert str(holder) in shown(signed_in(client, manager).get(address))
    assert client.post(address).status_code == 302
    assert not Group.objects.filter(pk=bundle.pk).exists()


def test_a_bundle_you_hold_yourself_is_not_deleted_by_you(
    client: Client, make_staff: Any, make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    make_user('clearance.permission_edit')
    bundle = make_bundle({'clearance.permission_view': None}, name='Mine')
    holder = make_staff(*MANAGER, bundles=(bundle,))

    response = signed_in(client, holder).post(
        f'/admin/access/bundles/{bundle.pk}/delete/', follow=True
    )

    assert Group.objects.filter(pk=bundle.pk).exists()
    assert notices(response)


def test_the_bundle_list_counts_what_each_holds_and_whom_it_reaches(
    client: Client, manager: Person, make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    bundle = make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': 'all'}, name='Editors')
    make_user(bundles=(bundle,))
    (row,) = signed_in(client, manager).get('/admin/access/bundles/').context['bundles']

    assert (row.name, row.held, row.people) == ('Editors', 2, 1)


# ---------------------------------------------------------------- the grid


def test_the_grid_lays_out_each_model_with_a_scope_only_where_one_can_be_chosen() -> None:
    ScopeRule.objects.create(
        content_type=ContentType.objects.get_for_model(Loan),
        code='large',
        name='Large loans',
        conditions=[{'field': 'amount', 'operator': 'at_least', 'value': {'constant': 1}}],
    )
    grid = PermissionGrid.build({'lending.loan_view': 'large'})
    (loans,) = [row for row in grid.rows if row.model is Loan]
    view = loans.columns[0]
    others = {cell.name: cell for cell in loans.others}

    assert view is not None
    assert (view.name, view.ticked, view.scope) == ('lending.loan_view', True, 'large')
    assert dict(view.scopes or {}) == {
        'all': 'Every row',
        'own': 'Their own loans',
        'reviewing': 'The loans they review',
        'large': 'Large loans',
    }
    assert others['lending.loan_view_credit_score'].scopes is None, "a field's takes none"
    assert 'lending.loan_approve' in others
    assert loans.label == 'Lending: loans'


def test_the_grid_is_read_in_a_fixed_number_of_queries(
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(4):  # permissions, rules, what is protected, the names
        PermissionGrid.build({})


def test_a_submitted_grid_is_its_ticks_with_their_scopes() -> None:
    assert PermissionGrid.parse(['a.x', 'a.y'], {'a.x': 'own', 'a.y': '', 'a.z': 'all'}) == {
        'a.x': 'own',
        'a.y': None,
    }


# ---------------------------------------------------------------- people


def test_the_people_list_shows_whoever_has_access_and_finds_anybody(
    client: Client, manager: Person, make_user: MakeUser
) -> None:
    nobody = make_user()
    nobody.first_name = 'Zahra'
    nobody.save()

    listed = [
        person.pk
        for person in signed_in(client, manager).get('/admin/access/people/').context['page']
    ]
    assert manager.pk in listed
    assert nobody.pk not in listed

    found = client.get('/admin/access/people/', {'q': 'zahr'}).context['page']
    assert [person.pk for person in found] == [nobody.pk]


def test_a_persons_page_shows_their_whole_standing(
    client: Client, manager: Person, make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    readers = make_bundle({'lending.loan_view': 'own'}, name='Readers')
    person = make_user(('lending.loan_view', 'all'), bundles=(readers,))
    AccessService(actor=None).revoke(person, 'lending.loan_edit', reason='under review')

    html = shown(signed_in(client, manager).get(f'/admin/access/people/{person.pk}/'))

    assert 'Readers' in html
    assert 'under review' in html
    assert 'their own grant' in html


def change(client: Client, person: Person, **data: Any) -> Any:
    return client.post(f'/admin/access/people/{person.pk}/', data, follow=True)


def test_bundles_and_permissions_are_given_and_taken_from_a_persons_page(
    client: Client, manager: Person, make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    readers = make_bundle({'lending.loan_view': 'all'}, name='Readers')
    person = make_user()
    signed_in(client, manager)

    change(client, person, do='give', bundle=readers.pk)
    assert list(person.groups.all()) == [readers]

    change(client, person, do='take', bundle=readers.pk)
    assert not person.groups.exists()

    change(client, person, do='grant', permission='lending.loan_view', scope='own')
    assert ScopeGrant.objects.get(user=person).scope == 'own'

    change(client, person, do='revoke', permission='lending.loan_view', reason='left')
    assert not person.user_permissions.exists()

    response = change(client, person, do='restore', permission='lending.loan_view')
    assert notices(response) == ['The permission was given back.']


def test_a_change_the_rules_refuse_says_so_on_the_page(client: Client, manager: Person) -> None:
    response = change(
        signed_in(client, manager), manager, do='grant', permission='lending.loan_delete'
    )

    assert not manager.user_permissions.filter(codename='loan_delete').exists()
    assert any('own' in message for message in notices(response))


@pytest.mark.parametrize(
    ('data', 'notice'),
    [
        ({}, 'Nothing was asked for.'),
        ({'do': 'grant', 'permission': 'no.such'}, 'no such permission'),
    ],
)
def test_a_change_that_makes_no_sense_says_so(
    client: Client, manager: Person, make_user: MakeUser, data: dict[str, str], notice: str
) -> None:
    response = change(signed_in(client, manager), make_user(), **data)

    assert any(notice in message for message in notices(response))


# ---------------------------------------------------------------- one person, read


def test_a_standing_names_where_each_permission_comes_from(
    make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    readers = make_bundle({'lending.loan_view': 'own', 'lending.loan_edit': None}, name='Readers')
    person = make_user(('lending.loan_view', 'all'), bundles=(readers,))
    AccessService(actor=None).revoke(person, 'lending.loan_edit', reason='under review')

    standing = Standing.of(person)
    (view,) = [held for held in standing.allowed if held.name == 'lending.loan_view']

    assert [(source.direct, source.scope) for source in view.sources] == [
        (False, 'own'),
        (True, 'all'),
    ]
    assert 'lending.loan_edit' not in {held.name for held in standing.allowed}
    assert [row.reason for row in standing.revocations] == ['under review']
    assert not standing.superuser


def test_a_standing_is_read_in_a_fixed_number_of_queries(
    make_bundle: MakeBundle,
    make_user: MakeUser,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    bundles = [make_bundle({'lending.loan_view': 'all'}, name=f'B{n}') for n in range(3)]
    person = Person.objects.get(pk=make_user('lending.loan_edit', bundles=bundles).pk)

    with django_assert_num_queries(
        8
    ):  # bundles, starting, theirs, own, scopes, taken, ceiling, roles
        Standing.of(person)


# ---------------------------------------------------------------- permissions


def test_the_permission_list_says_who_holds_each_and_how(
    client: Client, manager: Person, make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    make_bundle({'lending.loan_approve': 'all'}, name='Officers')
    person = make_user('lending.loan_approve')
    AccessService(actor=None).revoke(person, 'lending.loan_approve')

    permissions = (
        signed_in(client, manager).get('/admin/access/permissions/').context['permissions']
    )
    (approve,) = [found for found in permissions if found.codename == 'loan_approve']

    assert [bundle.name for bundle in approve.group_set.all()] == ['Officers']
    assert (approve.people, approve.taken) == (0, 1)


def test_the_permission_list_shows_those_nobody_holds(client: Client, manager: Person) -> None:
    unheld = signed_in(client, manager).get('/admin/access/permissions/', {'held': 'nobody'})
    names = {found.codename for found in unheld.context['permissions']}

    assert 'loan_remind' in names
    assert 'permission_view' not in names, 'the manager holds it'


def test_the_site_offers_its_pages_on_the_index_and_its_own_apps_page_only(
    make_staff: Any,
) -> None:
    request = RequestFactory().get('/')
    request.user = make_staff('clearance.permission_view', 'lending.view_payment')

    assert [app['app_label'] for app in admin.site.get_app_list(request, 'lending')] == ['lending']
    assert 'clearance' in [app['app_label'] for app in admin.site.get_app_list(request)]


def test_a_permission_of_a_model_that_is_gone_is_left_out_of_the_grid() -> None:
    from django.contrib.auth.models import Permission

    gone = ContentType.objects.create(app_label='lending', model='overdraft')
    Permission.objects.create(content_type=gone, codename='overdraft_view', name='Can view')

    assert all(row.model._meta.model_name != 'overdraft' for row in PermissionGrid.build({}).rows)
