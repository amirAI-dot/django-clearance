"""
A person reaches the rows the scopes of their grants give them, and no others.

If these fail, a list shows somebody else's loans, a grant nobody finished
shows everything instead of nothing, a scope chosen for one action leaks into
another, or a list costs a query per scope.
"""

from typing import Any, ClassVar

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from pytest_django import DjangoAssertNumQueries

from clearance.models import ScopeGrant
from clearance.protocols import User
from clearance.querysets import OwnedQuerySet, ScopedQuerySet, SignedInReadQuerySet
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment


@pytest.fixture
def ana(make_user: MakeUser) -> Person:
    return make_user()


@pytest.fixture
def officer(make_user: MakeUser) -> Person:
    return make_user()


@pytest.fixture
def loans(ana: Person, officer: Person, make_user: MakeUser) -> dict[str, Loan]:
    return {
        'ana': Loan.objects.create(applicant=ana, officer=officer, amount=100),
        'other': Loan.objects.create(applicant=make_user(), amount=200),
    }


def granted(person: Person, name: str, scope: str | None = None) -> Person:
    """``person``, given ``name`` directly in ``scope``, read back fresh."""
    person.user_permissions.add(permission(name))

    if scope is not None:
        ScopeGrant.objects.create(user=person, permission=permission(name), scope=scope)

    return Person.objects.get(pk=person.pk)


def given(person: Person, *bundles: Any) -> Person:
    """``person``, given ``bundles``, read back fresh."""
    person.groups.add(*bundles)
    return Person.objects.get(pk=person.pk)


def visible(queryset: ScopedQuerySet[Any], user: User, action: str = 'view') -> set[int]:
    return set(queryset.visible_to(user, action).values_list('pk', flat=True))


def pks(*rows: Any) -> set[int]:
    return {row.pk for row in rows}


# ---------------------------------------------------------------- the scopes


def test_own_reaches_the_persons_own_rows(ana: Person, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), granted(ana, 'lending.loan_view', 'own')) == pks(
        loans['ana']
    )


def test_a_scope_reaches_the_rows_its_method_names(
    officer: Person, make_bundle: MakeBundle, loans: dict[str, Loan]
) -> None:
    person = given(officer, make_bundle({'lending.loan_view': 'reviewing'}))

    assert visible(Loan.objects.all(), person) == pks(loans['ana'])


def test_all_reaches_every_row(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), make_user(('lending.loan_view', 'all'))) == pks(
        *loans.values()
    )


def test_the_superuser_reaches_every_row(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), make_user(superuser=True)) == pks(*loans.values())


def test_a_grant_with_no_scope_reaches_no_rows_when_no_default_is_named(
    make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), make_user('lending.loan_view')) == set()


def test_a_grant_with_no_scope_reaches_the_default_scope(
    ana: Person, loans: dict[str, Loan], make_bundle: MakeBundle
) -> None:
    mine = Payment.objects.create(loan=loans['ana'], amount=10)
    Payment.objects.create(loan=loans['other'], amount=20)
    person = given(ana, make_bundle({'lending.view_payment': None}))

    assert visible(Payment.objects.all(), person) == pks(mine)


def test_a_scope_the_model_no_longer_offers_reaches_nothing(
    make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    person = make_user(('lending.loan_view', 'removed_since'))

    assert visible(Loan.objects.all(), person) == set()


# ---------------------------------------------------------------- what is held


def test_without_the_actions_permission_no_rows_whatever_the_scope(
    make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), make_user(('lending.loan_edit', 'all'))) == set()


def test_each_action_has_its_own_scope(
    officer: Person, make_bundle: MakeBundle, loans: dict[str, Loan]
) -> None:
    person = given(
        officer, make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': 'reviewing'})
    )

    assert visible(Loan.objects.all(), person, 'view') == pks(*loans.values())
    assert visible(Loan.objects.all(), person, 'edit') == pks(loans['ana'])


def test_the_scopes_of_every_grant_join_into_their_union(
    officer: Person, make_bundle: MakeBundle, loans: dict[str, Loan]
) -> None:
    own = Loan.objects.create(applicant=officer, amount=300)
    given(officer, make_bundle({'lending.loan_view': 'reviewing'}))
    person = granted(officer, 'lending.loan_view', 'own')

    assert visible(Loan.objects.all(), person) == pks(own, loans['ana'])


def test_somebody_signed_out_or_switched_off_reaches_nothing(
    anonymous: AnonymousUser, make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), anonymous) == set()
    assert (
        visible(Loan.objects.all(), make_user(('lending.loan_view', 'all'), active=False)) == set()
    )
    assert visible(Loan.objects.all(), make_user(superuser=True, active=False)) == set()


def test_scoping_narrows_a_queryset_already_filtered(
    make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    person = make_user(('lending.loan_view', 'all'))

    assert visible(Loan.objects.filter(amount__gt=150), person) == pks(loans['other'])


# ---------------------------------------------------------------- what a scope answers


class AnsweringWithQuerysets(ScopedQuerySet[Loan]):
    scopes: ClassVar = {'own': 'Own', 'reviewing': 'Reviewing'}

    def scope_own(self, user: User) -> 'ScopedQuerySet[Loan]':
        return self.filter(applicant=user)

    def scope_reviewing(self, user: User) -> 'ScopedQuerySet[Loan]':
        return self.filter(officer=user)


class AnsweringWrongly(ScopedQuerySet[Loan]):
    scopes: ClassVar = {'people': 'People', 'text': 'Text', 'everything': 'Everything'}

    def scope_people(self, user: User) -> object:
        return Person.objects.all()

    def scope_text(self, user: User) -> object:
        return 'everything'

    def scope_everything(self, user: User) -> Q:
        return Q()


def test_a_scope_may_answer_with_a_queryset(officer: Person, loans: dict[str, Loan]) -> None:
    person = granted(officer, 'lending.loan_view', 'reviewing')

    assert visible(AnsweringWithQuerysets(model=Loan), person) == pks(loans['ana'])


def test_querysets_from_several_scopes_combine(
    officer: Person, make_bundle: MakeBundle, loans: dict[str, Loan]
) -> None:
    own = Loan.objects.create(applicant=officer, amount=300)
    person = given(
        officer,
        make_bundle({'lending.loan_view': 'reviewing'}),
        make_bundle({'lending.loan_view': 'own'}),
    )

    assert visible(AnsweringWithQuerysets(model=Loan), person) == pks(own, loans['ana'])


def test_an_empty_q_is_every_row(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    person = make_user(('lending.loan_view', 'everything'))

    assert visible(AnsweringWrongly(model=Loan), person) == pks(*loans.values())


def test_a_scope_answering_with_another_models_rows_is_an_error(make_user: MakeUser) -> None:
    with pytest.raises(TypeError, match='rows of Person, not Loan'):
        AnsweringWrongly(model=Loan).visible_to(make_user(('lending.loan_view', 'people')))


def test_a_scope_answering_with_anything_else_is_an_error(make_user: MakeUser) -> None:
    with pytest.raises(TypeError, match='answered with str'):
        AnsweringWrongly(model=Loan).visible_to(make_user(('lending.loan_view', 'text')))


# ---------------------------------------------------------------- what it costs


def test_a_scoped_list_costs_the_grants_once_and_the_list_once(
    officer: Person,
    make_bundle: MakeBundle,
    loans: dict[str, Loan],
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    person = given(
        officer,
        make_bundle({'lending.loan_view': 'reviewing'}),
        make_bundle({'lending.loan_view': 'own'}),
    )

    with django_assert_num_queries(2):
        list(Loan.objects.visible_to(person))

    with django_assert_num_queries(1):
        list(Loan.objects.visible_to(person, 'view'))


# ---------------------------------------------------------------- the ready-made querysets


def test_reference_data_is_reached_by_anybody_signed_in(
    make_user: MakeUser, anonymous: AnonymousUser, loans: dict[str, Loan]
) -> None:
    everything = SignedInReadQuerySet(model=Loan)

    assert visible(everything, make_user()) == pks(*loans.values())
    assert visible(everything, anonymous) == set()
    assert visible(everything, make_user(active=False)) == set()


class OwnedLoans(OwnedQuerySet[Loan]):
    owner_path = 'applicant'


def test_owned_rows_offer_own_beside_all(ana: Person, loans: dict[str, Loan]) -> None:
    person = granted(ana, 'lending.loan_view', 'own')

    assert set(OwnedLoans.offered_scopes()) == {'all', 'own'}
    assert visible(OwnedLoans(model=Loan), person) == pks(loans['ana'])
