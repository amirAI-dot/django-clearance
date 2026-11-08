"""
A role starts a person with bundles, and its ceiling stops what any bundle or
grant would give beyond it - inside the one query every check makes.

If these fail, a customer given a manager's bundle by mistake approves loans
their role never allows, a nurse's role gives them nothing it promises, a
role is read from the wrong place, or asking about roles costs a query per
permission.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from pytest_django import DjangoAssertNumQueries

from clearance import limits as limits_module
from clearance.grants import grants_of
from clearance.limits import Limits, install, limits, uninstall
from clearance.querysets import visible
from clearance.roles.checks import order_errors, resolver_errors
from clearance.roles.models import Role, RoleAssignment, RoleBundle, RoleCeiling
from clearance.roles.resolvers import has_role, resolver, roles_of
from clearance.safety import holders_of, somebody_holds
from clearance.services import AccessService
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan

pytestmark = pytest.mark.django_db

ATTRIBUTE = {
    'ROLE_RESOLVER': 'clearance.roles.resolvers.AttributeResolver',
    'ROLE_ATTRIBUTE': 'region',
}


def make_role(code: str, *ceiling: str, limited: bool = True, bundles: Any = ()) -> Role:
    role = Role.objects.create(code=code, name=code.title(), limited=limited)
    RoleCeiling.objects.bulk_create(
        RoleCeiling(role=role, permission=permission(p)) for p in ceiling
    )
    RoleBundle.objects.bulk_create(RoleBundle(role=role, group=group) for group in bundles)
    return role


def given(person: Person, *roles: Role) -> Person:
    for role in roles:
        RoleAssignment.objects.create(user=person, role=role)
    return Person.objects.get(pk=person.pk)


@pytest.fixture
def editors(make_bundle: MakeBundle) -> Group:
    return make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': 'all'}, name='Editors')


# ---------------------------------------------------------------- the ceiling


def test_a_ceiling_stops_what_a_bundle_gives_beyond_it(make_user: MakeUser, editors: Group) -> None:
    person = given(make_user(bundles=(editors,)), make_role('customer', 'lending.loan_view'))

    assert person.has_perm('lending.loan_view')
    assert not person.has_perm('lending.loan_edit')
    assert grants_of(person).holds('lending.loan_view')
    assert not grants_of(person).holds('lending.loan_edit')


def test_a_ceiling_stops_a_grant_to_the_person_too(make_user: MakeUser) -> None:
    person = given(make_user('lending.loan_delete'), make_role('customer', 'lending.loan_view'))

    assert not person.has_perm('lending.loan_delete')
    assert not grants_of(person).holds('lending.loan_delete')


def test_a_limited_role_with_nothing_in_its_ceiling_allows_nothing(
    make_user: MakeUser, editors: Group
) -> None:
    person = given(make_user(bundles=(editors,)), make_role('new'))

    assert person.get_all_permissions() == set()


@pytest.mark.parametrize(
    ('roles', 'edit'),
    [
        ([], True),
        ([('customer', True)], False),
        ([('customer', True), ('editor', True)], True),
        ([('customer', True), ('staff', False)], True),
    ],
    ids=['no role, no ceiling', 'one ceiling', 'the union of two', 'one role with none'],
)
def test_a_person_is_limited_by_the_union_of_their_roles_ceilings(
    make_user: MakeUser, editors: Group, roles: list[tuple[str, bool]], edit: bool
) -> None:
    ceilings = {'customer': ('lending.loan_view',), 'editor': ('lending.loan_edit',), 'staff': ()}
    made = [make_role(code, *ceilings[code], limited=limited) for code, limited in roles]
    person = given(make_user(bundles=(editors,)), *made)

    assert person.has_perm('lending.loan_view')
    assert person.has_perm('lending.loan_edit') is edit


def test_the_rows_reached_are_within_the_ceiling(make_user: MakeUser, editors: Group) -> None:
    person = given(make_user(bundles=(editors,)), make_role('customer', 'lending.loan_view'))
    Loan.objects.create(applicant=person, amount=1)

    assert visible(Loan.objects.all(), person, 'view').count() == 1
    assert visible(Loan.objects.all(), person, 'edit').count() == 0


def test_the_superuser_has_no_ceiling(make_user: MakeUser) -> None:
    person = given(make_user(superuser=True), make_role('customer'))

    assert person.has_perm('lending.loan_delete')


# ---------------------------------------------------------------- starting bundles


def test_a_role_starts_whoever_has_it_with_its_bundles(make_user: MakeUser, editors: Group) -> None:
    person = given(make_user(), make_role('clerk', limited=False, bundles=(editors,)))

    assert person.has_perm('lending.loan_edit')
    assert grants_of(person).scopes('lending.loan_edit') == {'all'}


def test_a_permission_taken_away_is_taken_from_a_starting_bundle_too(
    make_user: MakeUser, editors: Group
) -> None:
    person = given(make_user(), make_role('clerk', limited=False, bundles=(editors,)))
    AccessService(actor=None).revoke(person, 'lending.loan_edit')
    person = Person.objects.get(pk=person.pk)

    assert not person.has_perm('lending.loan_edit')
    assert not grants_of(person).holds('lending.loan_edit')


def test_a_starting_bundle_is_within_the_ceiling_like_any_other(
    make_user: MakeUser, editors: Group
) -> None:
    role = make_role('clerk', 'lending.loan_view', bundles=(editors,))
    person = given(make_user(), role)

    assert person.get_all_permissions() == {'lending.loan_view'}


# ---------------------------------------------------------------- what it costs


def test_roles_cost_no_query_of_their_own(
    make_user: MakeUser, editors: Group, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    role = make_role('clerk', 'lending.loan_view', bundles=(editors,))
    person = given(make_user('lending.loan_create', bundles=(editors,)), role)

    with django_assert_num_queries(2):  # Django's two: their own, and their bundles'
        person.has_perm('lending.loan_view')

    with django_assert_num_queries(1):
        grants_of(person)


# ---------------------------------------------------------------- whose job


def test_a_persons_roles_are_read_once_and_answer_whose_job_an_act_is(
    make_user: MakeUser, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    person = given(make_user(), make_role('nurse'), make_role('doctor'))

    with django_assert_num_queries(1):
        assert roles_of(person) == {'nurse', 'doctor'}
        assert has_role(person, 'nurse')
        assert has_role(person, 'midwife', 'doctor')
        assert not has_role(person, 'midwife')


def test_nobody_signed_out_or_switched_off_has_a_role(make_user: MakeUser) -> None:
    from django.contrib.auth.models import AnonymousUser

    off = given(make_user(active=False), make_role('nurse'))

    assert roles_of(off) == frozenset()
    assert roles_of(AnonymousUser()) == frozenset()
    assert not has_role(make_user(superuser=True), 'nurse'), 'a role is not a power'


# ---------------------------------------------------------------- read from the user model


@override_settings(CLEARANCE=ATTRIBUTE)
def test_roles_can_be_read_from_a_field_of_the_user(make_user: MakeUser, editors: Group) -> None:
    make_role('north', 'lending.loan_view')
    person = make_user(bundles=(editors,))
    person.region = 'north'
    person.save()
    person = Person.objects.get(pk=person.pk)

    assert roles_of(person) == {'north'}
    assert not person.has_perm('lending.loan_edit')
    assert list(resolver().holders(Role.objects.filter(code='north'))) == [person]


@override_settings(CLEARANCE=ATTRIBUTE)
def test_a_person_whose_field_names_no_role_has_none(make_user: MakeUser) -> None:
    assert roles_of(make_user()) == frozenset()


# ---------------------------------------------------------------- the safety rules see it


def test_somebody_whose_ceiling_stops_managing_does_not_count_as_managing(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    managers = make_bundle({'clearance.permission_edit': None}, name='Managers')
    manager = given(make_user(bundles=(managers,)), make_role('customer', 'lending.loan_view'))

    assert manager in holders_of('clearance.permission_edit')
    assert not somebody_holds('clearance.permission_edit')


def test_somebody_starting_with_a_managers_bundle_counts(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    managers = make_bundle({'clearance.permission_edit': None}, name='Managers')
    manager = given(make_user(), make_role('admin', limited=False, bundles=(managers,)))

    assert list(holders_of('clearance.permission_edit')) == [manager]
    assert somebody_holds('clearance.permission_edit')


# ---------------------------------------------------------------- without roles


@pytest.fixture
def no_roles() -> Iterator[None]:
    installed = limits()
    uninstall()
    yield
    install(installed)


def test_without_roles_nothing_starts_and_nothing_is_stopped(
    no_roles: None, make_user: MakeUser, editors: Group
) -> None:
    person = given(make_user(bundles=(editors,)), make_role('customer'))

    assert person.has_perm('lending.loan_edit')
    assert type(limits_module.limits()) is Limits
    assert list(Limits().people_starting_with(Group.objects.all())) == []
    assert Limits().describe(person) == []


# ---------------------------------------------------------------- at start-up


def test_roles_installed_without_the_core_or_before_it_are_refused() -> None:
    assert [error.id for error in order_errors(['clearance_roles'])] == ['clearance.E008']
    assert [error.id for error in order_errors(['clearance_roles', 'clearance'])] == [
        'clearance.E008'
    ]
    assert order_errors(['clearance', 'clearance_roles']) == []
    assert order_errors(['clearance']) == []


@pytest.mark.parametrize(
    ('setting', 'message'),
    [
        ({'ROLE_RESOLVER': 'not.a.Resolver'}, 'cannot be used'),
        ({'ROLE_RESOLVER': 'clearance.roles.models.Role'}, 'is not a RoleResolver'),
        ({**ATTRIBUTE, 'ROLE_ATTRIBUTE': 'colour'}, "'colour', which is not a field"),
    ],
)
def test_a_resolver_that_cannot_be_used_is_refused_at_start_up(
    setting: dict[str, str], message: str
) -> None:
    with override_settings(CLEARANCE=setting):
        errors = resolver_errors()

    assert [error.id for error in errors] == ['clearance.E010']
    assert message in errors[0].msg


def test_the_project_reads_roles_from_where_it_can() -> None:
    assert resolver_errors() == []
    with override_settings(CLEARANCE=ATTRIBUTE):
        assert resolver_errors() == []


def test_each_row_says_what_it_is(make_user: MakeUser, editors: Group) -> None:
    role = make_role('clerk', 'lending.loan_view', bundles=(editors,))
    given(make_user(), role)

    assert str(role) == 'Clerk'
    assert str(role.assignments.get()).endswith(': Clerk')
    assert str(role.ceiling.get()) == f'Clerk: {permission("lending.loan_view")}'
    assert str(role.bundles.get()) == 'Clerk: Editors'
