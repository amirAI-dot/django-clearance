"""
A person holds what their bundles give them, less what was taken from them alone.

If these fail, a bundle given to somebody gives them nothing, a permission
taken away from one person is still held - by them, or taken from everybody
else in the bundle too - or asking costs more than Django's own backend.
"""

from django.contrib.auth.models import AnonymousUser
from pytest_django import DjangoAssertNumQueries

from clearance.grants import forget_grants, grants_of
from clearance.models import PermissionRevocation
from tests.conftest import MakeBundle, MakeUser, permission


def test_a_bundle_gives_everybody_holding_it_what_it_holds(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    officers = make_bundle({'lending.loan_view': 'all', 'lending.loan_approve': 'reviewing'})
    ana, bob = make_user(bundles=(officers,)), make_user(bundles=(officers,))

    assert ana.has_perm('lending.loan_approve')
    assert bob.has_perm('lending.loan_view')


def test_a_person_may_hold_several_bundles(make_user: MakeUser, make_bundle: MakeBundle) -> None:
    readers = make_bundle({'lending.loan_view': 'all'})
    payers = make_bundle({'lending.view_payment': None})
    person = make_user(bundles=(readers, payers))

    assert person.has_perm('lending.loan_view')
    assert person.has_perm('lending.view_payment')
    assert not person.has_perm('lending.loan_edit')


def test_a_revocation_takes_one_permission_from_one_person(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    officers = make_bundle({'lending.loan_view': 'all', 'lending.loan_approve': 'all'})
    ana, bob = make_user(bundles=(officers,)), make_user(bundles=(officers,))
    PermissionRevocation.objects.create(user=ana, permission=permission('lending.loan_approve'))
    forget_grants(ana)

    assert not ana.has_perm('lending.loan_approve')
    assert ana.has_perm('lending.loan_view'), 'the rest of the bundle still reaches her'
    assert bob.has_perm('lending.loan_approve'), 'nobody else lost anything'


def test_a_revocation_does_not_cancel_a_direct_grant(make_user: MakeUser) -> None:
    person = make_user('lending.loan_view')
    PermissionRevocation.objects.create(user=person, permission=permission('lending.loan_view'))
    forget_grants(person)

    assert person.has_perm('lending.loan_view'), 'revoking a direct grant removes it instead'


def test_grants_say_with_which_scopes_a_permission_is_held(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    reviewers = make_bundle({'lending.loan_view': 'reviewing'})
    unscoped = make_bundle({'lending.loan_view': None})
    person = make_user(('lending.loan_view', 'own'), bundles=(reviewers, unscoped))

    assert grants_of(person).scopes('lending.loan_view') == {'own', 'reviewing', None}
    assert grants_of(person).scopes('lending.loan_edit') is None


def test_a_revoked_permission_has_no_scopes_left_from_bundles(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    person = make_user(bundles=(make_bundle({'lending.loan_view': 'all'}),))
    PermissionRevocation.objects.create(user=person, permission=permission('lending.loan_view'))

    assert not grants_of(person).holds('lending.loan_view')


def test_somebody_signed_out_or_switched_off_holds_nothing(
    make_user: MakeUser, anonymous: AnonymousUser
) -> None:
    assert not grants_of(anonymous).holds('lending.loan_view')
    assert not grants_of(make_user('lending.loan_view', active=False)).holds('lending.loan_view')


# ---------------------------------------------------------------- what it costs


def test_asking_costs_what_djangos_own_backend_costs(
    make_user: MakeUser,
    make_bundle: MakeBundle,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    person = make_user('lending.view_payment', bundles=(make_bundle({'lending.loan_view': 'all'}),))

    with django_assert_num_queries(2):  # the person's own, and their bundles' - as Django
        assert person.has_perm('lending.loan_view')
        assert person.has_perm('lending.view_payment')
        assert not person.has_perm('lending.loan_edit')


def test_a_persons_grants_are_read_once_per_request(
    make_user: MakeUser,
    make_bundle: MakeBundle,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    person = make_user(
        ('lending.view_payment', 'own'),
        bundles=(
            make_bundle({'lending.loan_view': 'all'}),
            make_bundle({'lending.loan_edit': None}),
        ),
    )

    with django_assert_num_queries(1):
        grants_of(person).scopes('lending.loan_view')
        grants_of(person).scopes('lending.view_payment')
        grants_of(person).holds('lending.loan_edit')
