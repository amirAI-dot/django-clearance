"""
Roles are made, given and limited only under the safety rules - in code and
on the roles pages alike.

If these fail, an administrator who manages bundles widens what a role may
hold, lifts a ceiling from somebody by taking their role away, changes what
their own role holds, or gives everybody with a role a bundle they never held.
"""

from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.dispatch import Signal
from django.test import Client, override_settings

from clearance.roles import signals
from clearance.roles.models import Role, RoleAssignment, RoleBundle, RoleCeiling
from clearance.roles.services import RoleService
from clearance.safety import AccessRefused
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person

pytestmark = pytest.mark.django_db

MANAGER = (
    'clearance.permission_view',
    'clearance.permission_create',
    'clearance.permission_edit',
    'clearance.permission_delete',
)


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    """Manages access, and may not touch a ceiling."""
    make_user('clearance.permission_edit')  # somebody else who manages access
    person = make_user(*MANAGER, ('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))
    person.is_staff = True
    person.save()
    return Person.objects.get(pk=person.pk)


@pytest.fixture
def ceiling_keeper(make_user: MakeUser) -> Person:
    """Manages access, and may change ceilings."""
    make_user('clearance.permission_edit')
    person = make_user(*MANAGER, 'clearance.role_ceiling_edit', ('lending.loan_view', 'all'))
    person.is_staff = True
    person.save()
    return Person.objects.get(pk=person.pk)


@pytest.fixture
def readers(make_bundle: MakeBundle) -> Group:
    return make_bundle({'lending.loan_view': 'all'}, name='Readers')


def refused(rule: str, act: Callable[[], Any]) -> None:
    with pytest.raises(AccessRefused) as refusal:
        act()
    assert refusal.value.rule == rule


# ---------------------------------------------------------------- making roles


def test_a_role_with_nothing_in_its_ceiling_is_made_by_whoever_may_create(
    manager: Person,
) -> None:
    role = RoleService(actor=manager).create_role('clerk', 'Clerk')

    assert (role.code, role.limited, role.ceiling.count()) == ('clerk', True, 0)


@pytest.mark.parametrize('ceiling', [None, ['lending.loan_view']], ids=['none', 'some'])
def test_a_role_made_with_a_ceiling_needs_the_ceiling_permission(
    manager: Person, ceiling_keeper: Person, ceiling: list[str] | None
) -> None:
    refused(
        'may_not_manage', lambda: RoleService(actor=manager).create_role('c', 'C', ceiling=ceiling)
    )

    role = RoleService(actor=ceiling_keeper).create_role('c', 'C', ceiling=ceiling)
    assert RoleService(actor=None).ceiling_of(role) == (None if ceiling is None else set(ceiling))


@pytest.mark.parametrize(
    ('code', 'ceiling', 'message'),
    [
        ('Clerk!', (), 'is not a code'),
        ('taken', (), "There is a role 'taken' already"),
        ('clerk', ('no.such',), 'no.such: no such permission'),
    ],
)
def test_a_role_that_cannot_be_made_says_why(
    ceiling_keeper: Person, code: str, ceiling: tuple[str, ...], message: str
) -> None:
    Role.objects.create(code='taken', name='Taken')

    with pytest.raises(ValidationError, match=message):
        RoleService(actor=ceiling_keeper).create_role(code, code, ceiling=ceiling)


def test_a_role_starts_people_only_with_bundles_its_maker_holds(
    manager: Person, make_bundle: MakeBundle, readers: Group
) -> None:
    deleters = make_bundle({'lending.loan_delete': 'all'}, name='Deleters')

    refused(
        'not_held', lambda: RoleService(actor=manager).create_role('c', 'C', bundles=[deleters])
    )
    role = RoleService(actor=manager).create_role('c', 'C', bundles=[readers])
    assert list(role.bundles.values_list('group__name', flat=True)) == ['Readers']


def test_renaming_changes_nobodys_access(manager: Person) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    RoleService(actor=manager).rename_role(role, 'Loan clerk')
    RoleService(actor=manager).rename_role(role, 'Loan clerk')

    assert Role.objects.get().name == 'Loan clerk'


# ---------------------------------------------------------------- ceilings


def test_a_ceiling_is_changed_only_with_its_permission(
    manager: Person, ceiling_keeper: Person
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')

    refused(
        'may_not_manage',
        lambda: RoleService(actor=manager).set_ceiling(role, ['lending.loan_view']),
    )
    RoleService(actor=ceiling_keeper).set_ceiling(role, ['lending.loan_view'])
    assert [row.permission for row in role.ceiling.all()] == [permission('lending.loan_view')]

    RoleService(actor=ceiling_keeper).set_ceiling(role, None)
    role.refresh_from_db()
    assert (role.limited, role.ceiling.count()) == (False, 0)


def test_nobody_changes_what_their_own_role_holds(ceiling_keeper: Person) -> None:
    role = Role.objects.create(code='admin', name='Admin', limited=False)
    RoleAssignment.objects.create(user=ceiling_keeper, role=role)
    keeper = Person.objects.get(pk=ceiling_keeper.pk)

    refused('own_role', lambda: RoleService(actor=keeper).set_ceiling(role, ['lending.loan_view']))
    refused('own_role', lambda: RoleService(actor=keeper).delete_role(role))


def test_a_ceiling_that_would_leave_nobody_managing_is_refused(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    managers = make_bundle({'clearance.permission_edit': None}, name='Managers')
    role = Role.objects.create(code='staff', name='Staff', limited=False)
    RoleAssignment.objects.create(user=make_user(bundles=(managers,)), role=role)

    refused('nobody_left', lambda: RoleService(actor=None).set_ceiling(role, ['lending.loan_view']))


def test_setting_the_ceiling_it_has_already_changes_nothing(ceiling_keeper: Person) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    RoleService(actor=ceiling_keeper).set_ceiling(role, [])

    assert role.ceiling.count() == 0


# ---------------------------------------------------------------- deleting


def test_deleting_a_limited_role_lifts_a_ceiling_and_needs_its_permission(
    manager: Person, ceiling_keeper: Person
) -> None:
    limited = Role.objects.create(code='clerk', name='Clerk')
    unlimited = Role.objects.create(code='staff', name='Staff', limited=False)

    refused('may_not_manage', lambda: RoleService(actor=manager).delete_role(limited))
    RoleService(actor=manager).delete_role(unlimited)
    RoleService(actor=ceiling_keeper).delete_role(limited)

    assert not Role.objects.exists()


# ---------------------------------------------------------------- starting bundles


def test_starting_bundles_are_given_and_taken_under_the_rules(
    manager: Person, make_bundle: MakeBundle, readers: Group
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    deleters = make_bundle({'lending.loan_delete': 'all'}, name='Deleters')
    roles = RoleService(actor=manager)

    roles.give_bundle(role, readers)
    roles.give_bundle(role, readers)
    refused('not_held', lambda: roles.give_bundle(role, deleters))
    assert RoleBundle.objects.filter(role=role).count() == 1

    roles.take_bundle(role, readers)
    roles.take_bundle(role, readers)
    assert not RoleBundle.objects.exists()


# ---------------------------------------------------------------- people


def test_a_role_is_given_and_taken_under_the_rules(
    manager: Person, ceiling_keeper: Person, make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    deleters = make_bundle({'lending.loan_delete': 'all'}, name='Deleters')
    clerk = Role.objects.create(code='clerk', name='Clerk')
    cleaner = Role.objects.create(code='cleaner', name='Cleaner', limited=False)
    RoleBundle.objects.create(role=cleaner, group=deleters)
    person = make_user()

    RoleService(actor=manager).assign(person, clerk)
    RoleService(actor=manager).assign(person, clerk)
    refused('not_held', lambda: RoleService(actor=manager).assign(person, cleaner))
    refused('own_access', lambda: RoleService(actor=manager).assign(manager, clerk))
    refused('may_not_manage', lambda: RoleService(actor=manager).unassign(person, clerk))

    RoleService(actor=ceiling_keeper).unassign(person, clerk)
    RoleService(actor=ceiling_keeper).unassign(person, clerk)
    assert not RoleAssignment.objects.exists()


@override_settings(
    CLEARANCE={
        'ROLE_RESOLVER': 'clearance.roles.resolvers.AttributeResolver',
        'ROLE_ATTRIBUTE': 'region',
    }
)
def test_a_role_read_from_the_user_model_is_not_given_here(
    manager: Person, make_user: MakeUser
) -> None:
    role = Role.objects.create(code='north', name='North')

    with pytest.raises(ValidationError, match='AttributeResolver'):
        RoleService(actor=manager).assign(make_user(), role)


# ---------------------------------------------------------------- announced


def test_every_change_is_announced_once_it_commits(
    ceiling_keeper: Person,
    make_user: MakeUser,
    readers: Group,
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    caught: list[str] = []
    every = [
        signals.role_saved,
        signals.role_deleted,
        signals.role_assigned,
        signals.role_unassigned,
        signals.ceiling_changed,
    ]
    names = {
        id(signal): name for name, signal in vars(signals).items() if isinstance(signal, Signal)
    }

    def receiver(signal: Signal, **kwargs: Any) -> None:
        caught.append(names[id(signal)])

    for signal in every:
        signal.connect(receiver, weak=False)

    try:
        with django_capture_on_commit_callbacks(execute=True):
            roles = RoleService(actor=None)
            role = roles.create_role('clerk', 'Clerk')
            roles.set_ceiling(role, ['lending.loan_view'])
            roles.give_bundle(role, readers)
            person = make_user()
            roles.assign(person, role)
            roles.unassign(person, role)
            roles.delete_role(role)
    finally:
        for signal in every:
            signal.disconnect(receiver)

    assert caught == [
        'role_saved',
        'ceiling_changed',
        'role_saved',
        'role_assigned',
        'role_unassigned',
        'role_deleted',
    ]


# ---------------------------------------------------------------- the pages


def page(client: Client, viewer: Person, address: str, **data: Any) -> Any:
    client.force_login(viewer)
    return client.post(address, data, follow=True) if data else client.get(address)


def notices(response: Any) -> list[str]:
    return [str(message) for message in response.context['messages']]


def test_the_roles_pages_need_the_permission_to_view_access(
    client: Client, make_user: MakeUser
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    staff = make_user()
    staff.is_staff = True
    staff.save()

    for address in (
        '/admin/access/roles/',
        f'/admin/access/roles/{role.pk}/',
        '/admin/access/roles/add/',
    ):
        assert page(client, staff, address).status_code == 403


def test_the_role_list_counts_each_ones_ceiling_bundles_and_people(
    client: Client, manager: Person, readers: Group, make_user: MakeUser
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    RoleCeiling.objects.create(role=role, permission=permission('lending.loan_view'))
    RoleBundle.objects.create(role=role, group=readers)
    RoleAssignment.objects.create(user=make_user(), role=role)

    (row,) = page(client, manager, '/admin/access/roles/').context['roles']
    assert (row.permitted, row.starting, row.people) == (1, 1, 1)
    assert '/admin/access/roles/' in page(client, manager, '/admin/').content.decode()


def test_a_role_is_made_from_its_page(client: Client, manager: Person) -> None:
    response = page(client, manager, '/admin/access/roles/add/', code='clerk', name='Clerk')

    assert Role.objects.get().name == 'Clerk'
    assert notices(response) == ['The role Clerk was made.']
    refusal = page(client, manager, '/admin/access/roles/add/', code='Clerk!')
    assert any('is not a code' in error for error in refusal.context['errors'])


def test_a_roles_page_changes_it_through_the_service(
    client: Client, ceiling_keeper: Person, readers: Group, make_user: MakeUser
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    person = make_user()
    person.username = 'sara'
    person.save()
    address = f'/admin/access/roles/{role.pk}/'

    page(client, ceiling_keeper, address, do='rename', name='Loan clerk')
    page(client, ceiling_keeper, address, do='ceiling', limited='on', permit=['lending.loan_view'])
    page(client, ceiling_keeper, address, do='give', bundle=readers.pk)
    page(client, ceiling_keeper, address, do='assign', person='sara')
    role.refresh_from_db()

    assert role.name == 'Loan clerk'
    assert RoleService(actor=None).ceiling_of(role) == {'lending.loan_view'}
    assert list(Group.objects.filter(role_bundles__role=role)) == [readers]
    assert list(role.assignments.values_list('user__username', flat=True)) == ['sara']

    html = page(client, ceiling_keeper, address).content.decode()
    assert 'value="lending.loan_view" checked' in html
    assert 'sara' in html

    page(client, ceiling_keeper, address, do='unassign', person=str(person.pk))
    page(client, ceiling_keeper, address, do='take', bundle=readers.pk)
    page(client, ceiling_keeper, address, do='ceiling')
    role.refresh_from_db()
    assert (role.limited, role.assignments.count(), role.bundles.count()) == (False, 0, 0)


def test_somebody_without_the_ceiling_permission_sees_it_but_cannot_change_it(
    client: Client, manager: Person
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    address = f'/admin/access/roles/{role.pk}/'

    html = page(client, manager, address).content.decode()
    assert 'name="permit"' in html
    assert 'Save the ceiling' not in html

    response = page(
        client, manager, address, do='ceiling', limited='on', permit=['lending.loan_view']
    )
    assert notices(response) == ["You may not change a role's ceiling."]


@pytest.mark.parametrize(
    ('data', 'notice'),
    [
        ({'do': 'nothing'}, 'Nothing was asked for.'),
        ({'do': 'assign', 'person': 'ghost'}, 'There is nobody called ghost.'),
    ],
)
def test_a_change_that_makes_no_sense_says_so(
    client: Client, manager: Person, data: dict[str, str], notice: str
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')

    assert notices(page(client, manager, f'/admin/access/roles/{role.pk}/', **data)) == [notice]


def test_a_role_is_deleted_from_its_page_under_the_rules(
    client: Client, manager: Person, ceiling_keeper: Person
) -> None:
    role = Role.objects.create(code='clerk', name='Clerk')
    address = f'/admin/access/roles/{role.pk}/delete/'

    assert 'its ceiling' in page(client, manager, address).content.decode()
    assert notices(page(client, manager, address, confirm='yes'))
    assert Role.objects.exists(), 'a ceiling is not lifted without its permission'

    page(client, ceiling_keeper, address, confirm='yes')
    assert not Role.objects.exists()


def test_a_persons_page_shows_their_roles_what_they_start_with_and_what_is_stopped(
    client: Client, manager: Person, make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    editors = make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': 'all'}, name='Editors')
    role = Role.objects.create(code='clerk', name='Clerk')
    RoleCeiling.objects.create(role=role, permission=permission('lending.loan_view'))
    RoleBundle.objects.create(role=role, group=editors)
    person = make_user()
    RoleAssignment.objects.create(user=person, role=role)

    response = page(client, manager, f'/admin/access/people/{person.pk}/')
    standing = response.context['standing']

    assert standing.roles == ['Clerk']
    assert [bundle.name for bundle in standing.starting] == ['Editors']
    assert [held.name for held in standing.allowed] == ['lending.loan_view']
    assert [held.name for held in standing.stopped] == ['lending.loan_edit']
    assert 'from their role' in response.content.decode()


@override_settings(
    CLEARANCE={
        'ROLE_RESOLVER': 'clearance.roles.resolvers.AttributeResolver',
        'ROLE_ATTRIBUTE': 'region',
    }
)
def test_a_role_read_from_the_user_model_is_not_offered_to_give(
    client: Client, manager: Person
) -> None:
    role = Role.objects.create(code='north', name='North')

    html = page(client, manager, f'/admin/access/roles/{role.pk}/').content.decode()
    assert 'Roles are read from each person' in html
    assert page(client, manager, '/admin/access/roles/').context['assigns'] is False


# ---------------------------------------------------------------- the edges


def test_taking_away_a_role_with_no_ceiling_needs_no_ceiling_permission(
    manager: Person, make_user: MakeUser
) -> None:
    role = Role.objects.create(code='staff', name='Staff', limited=False)
    person = make_user()
    RoleAssignment.objects.create(user=person, role=role)

    RoleService(actor=manager).unassign(person, role)

    assert not RoleAssignment.objects.exists()


def test_the_page_to_make_a_role_says_it_starts_with_nothing(
    client: Client, manager: Person
) -> None:
    html = page(client, manager, '/admin/access/roles/add/').content.decode()

    assert 'may hold nothing until its ceiling is set' in html


def test_a_permission_of_a_model_that_is_gone_is_not_offered_for_a_ceiling(
    client: Client, manager: Person
) -> None:
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    gone = ContentType.objects.create(app_label='lending', model='overdraft')
    Permission.objects.create(content_type=gone, codename='overdraft_view', name='Can view')
    role = Role.objects.create(code='clerk', name='Clerk')

    rows = page(client, manager, f'/admin/access/roles/{role.pk}/').context['rows']
    assert not any('overdraft' in name for _, cells in rows for name, _, _ in cells)


def test_pages_are_mounted_once_however_often_they_are_added() -> None:
    from clearance.admin.sites import ClearanceAdminSite
    from clearance.roles.pages import RolePages

    ClearanceAdminSite.add_pages(RolePages)

    assert ClearanceAdminSite.page_sets.count(RolePages) == 1


def test_a_set_of_pages_adds_nothing_to_the_index_unless_it_says_so() -> None:
    from django.contrib import admin
    from django.test import RequestFactory

    from clearance.admin.views import PageSet

    class Quiet(PageSet):
        def get_urls(self) -> list[Any]:
            return []

    assert Quiet(admin.site).menu(RequestFactory().get('/')) == []
