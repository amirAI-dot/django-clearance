"""
Somebody who holds a bundle by their role holds it on every access page:
the people, the overview's count, the bundle's holders, and what deleting it
takes from.

If these fail, the people page leaves out every branch manager whose access
comes from their role, a bundle half the staff starts with reads "Nobody
holds it", and deleting it is shown as taking from nobody - while it takes
from all of them.
"""

from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from pytest_django import DjangoAssertNumQueries

from clearance.roles.models import Role, RoleAssignment, RoleBundle
from tests.conftest import MakeBundle, MakeUser
from tests.project.accounts.models import Person

pytestmark = pytest.mark.django_db

LOOKER = ('clearance.permission_view', 'clearance.permission_delete')


@pytest.fixture
def editors(make_bundle: MakeBundle) -> Group:
    return make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': 'all'}, name='Editors')


@pytest.fixture
def editor_role(editors: Group) -> Role:
    role = Role.objects.create(code='editor', name='Editor', limited=False)
    RoleBundle.objects.create(role=role, group=editors)
    return role


@pytest.fixture
def looking(client: Client, make_user: MakeUser, editors: Group) -> Client:
    person = make_user(*LOOKER, ('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))
    person.is_staff = True
    person.save()
    client.force_login(person)
    return client


def by_role(role: Role, username: str) -> Person:
    person = Person.objects.create_user(username=username)
    RoleAssignment.objects.create(user=person, role=role)
    return person


def shown(response: Any) -> str:
    return response.content.decode()


def test_the_people_page_lists_somebody_whose_bundle_comes_from_their_role(
    looking: Client, make_user: MakeUser, editor_role: Role
) -> None:
    by_role(editor_role, 'roley')
    Person.objects.create_user(username='nobody_at_all')

    page = shown(looking.get('/admin/access/people/'))

    assert 'roley' in page
    assert 'from their role' in page
    assert 'nobody_at_all' not in page


def test_the_overview_counts_them_among_the_people_with_access(
    looking: Client, make_user: MakeUser, editor_role: Role
) -> None:
    before = looking.get('/admin/access/').context['people']
    by_role(editor_role, 'roley')

    assert looking.get('/admin/access/').context['people'] == before + 1


def test_a_bundle_names_whoever_starts_with_it_among_its_holders(
    looking: Client, make_user: MakeUser, editors: Group, editor_role: Role
) -> None:
    by_role(editor_role, 'roley')

    response = looking.get(f'/admin/access/bundles/{editors.pk}/')

    assert [person.username for person in response.context['starting']] == ['roley']
    assert 'roley' in shown(response)
    assert 'Nobody holds it.' not in shown(response)


def test_somebody_given_a_bundle_their_role_gives_too_is_named_once(
    looking: Client, make_user: MakeUser, editors: Group, editor_role: Role
) -> None:
    both = by_role(editor_role, 'both')
    both.groups.add(editors)

    response = looking.get(f'/admin/access/bundles/{editors.pk}/')

    assert [person.username for person in response.context['holders']] == ['both']
    assert response.context['starting'] == []


def test_deleting_a_bundle_says_it_takes_from_whoever_starts_with_it(
    looking: Client, make_user: MakeUser, editors: Group, editor_role: Role
) -> None:
    by_role(editor_role, 'roley')

    response = looking.get(f'/admin/access/bundles/{editors.pk}/delete/')

    assert [person.username for person in response.context['holders']] == ['roley']
    assert 'from the one person holding it' in shown(response)


def test_the_people_page_costs_the_same_however_many_start_with_a_bundle(
    looking: Client,
    make_user: MakeUser,
    editor_role: Role,
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> None:
    by_role(editor_role, 'first')
    looking.get('/admin/access/people/')

    with django_assert_max_num_queries(50) as few:
        looking.get('/admin/access/people/')

    for number in range(5):
        by_role(editor_role, f'more{number}')

    with django_assert_max_num_queries(len(few.captured_queries)):
        looking.get('/admin/access/people/')
