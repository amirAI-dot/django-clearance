"""
A person reaches the rows their roles give them, and no others.

If these fail, a list shows somebody else's loans, a role nobody wrote a rule
for sees everything instead of nothing, or a list costs a query per role.
"""

from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from django.test import override_settings
from pytest_django import DjangoAssertNumQueries

from clearance.protocols import User
from clearance.querysets import OwnedQuerySet, ScopedQuerySet, SignedInReadQuerySet
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan

SEVERAL_ROLES = override_settings(
    CLEARANCE={
        'ROLES': ['admin', 'officer', 'customer', 'auditor'],
        'EVERY_ROW_ROLES': ['admin'],
        'ROLE_ATTRIBUTE': 'roles',
    }
)


@pytest.fixture
def people(make_user: MakeUser) -> dict[str, Person]:
    return {
        'ana': make_user(role='customer'),
        'bob': make_user(role='customer'),
        'officer': make_user(role='officer'),
    }


@pytest.fixture
def loans(people: dict[str, Person]) -> dict[str, Loan]:
    return {
        'ana': Loan.objects.create(applicant=people['ana'], officer=people['officer'], amount=100),
        'bob': Loan.objects.create(applicant=people['bob'], amount=200),
    }


def visible(queryset: ScopedQuerySet[Any], user: User) -> set[int]:
    return set(queryset.visible_to(user).values_list('pk', flat=True))


def pks(*loans: Loan) -> set[int]:
    return {loan.pk for loan in loans}


# ---------------------------------------------------------------- who reaches what


def test_a_customer_reaches_their_own_loans(
    people: dict[str, Person], loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), people['ana']) == pks(loans['ana'])


def test_an_officer_reaches_the_loans_they_review(
    people: dict[str, Person], loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), people['officer']) == pks(loans['ana'])


def test_an_every_row_role_reaches_every_row(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), make_user(role='admin')) == pks(*loans.values())


def test_the_superuser_reaches_every_row(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), make_user(superuser=True)) == pks(*loans.values())


def test_a_role_with_no_hook_reaches_nothing(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), make_user(role='auditor')) == set()


def test_somebody_with_no_role_reaches_nothing(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    assert visible(Loan.objects.all(), make_user()) == set()


def test_somebody_signed_out_reaches_nothing(
    anonymous: AnonymousUser, loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), anonymous) == set()


def test_a_switched_off_account_reaches_nothing(
    make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.all(), make_user(role='admin', active=False)) == set()
    assert visible(Loan.objects.all(), make_user(superuser=True, active=False)) == set()


@SEVERAL_ROLES
def test_several_roles_reach_the_union_of_their_rows(
    make_user: MakeUser, people: dict[str, Person], loans: dict[str, Loan]
) -> None:
    both = make_user(role='officer', extra_roles=['customer'])
    own = Loan.objects.create(applicant=both, amount=300)
    loans['bob'].officer = both
    loans['bob'].save()

    assert visible(Loan.objects.all(), both) == pks(own, loans['bob'])


@SEVERAL_ROLES
def test_one_every_row_role_among_several_reaches_every_row(
    make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    person = make_user(role='customer', extra_roles=['admin'])

    assert visible(Loan.objects.all(), person) == pks(*loans.values())


def test_scoping_narrows_a_queryset_already_filtered(
    people: dict[str, Person], loans: dict[str, Loan]
) -> None:
    assert visible(Loan.objects.filter(amount__gt=150), people['ana']) == set()


# ---------------------------------------------------------------- what a hook answers


class AnsweringWithQuerysets(ScopedQuerySet[Loan]):
    def scope_for_customer(self, user: User) -> 'ScopedQuerySet[Loan]':
        return self.filter(applicant=user)

    def scope_for_officer(self, user: User) -> 'ScopedQuerySet[Loan]':
        return self.filter(officer=user)


def test_a_hook_may_answer_with_a_queryset(
    people: dict[str, Person], loans: dict[str, Loan]
) -> None:
    queryset = AnsweringWithQuerysets(model=Loan)

    assert visible(queryset, people['ana']) == pks(loans['ana'])


@SEVERAL_ROLES
def test_querysets_from_several_roles_combine(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    both = make_user(role='officer', extra_roles=['customer'])
    own = Loan.objects.create(applicant=both, amount=300)
    reviewed = Loan.objects.create(applicant=make_user(), officer=both, amount=400)

    assert visible(AnsweringWithQuerysets(model=Loan), both) == pks(own, reviewed)


class AnsweringWithEverything(ScopedQuerySet[Loan]):
    def scope_for_auditor(self, user: User) -> Q:
        return Q()


def test_an_empty_q_is_every_row(make_user: MakeUser, loans: dict[str, Loan]) -> None:
    auditor = make_user(role='auditor')

    assert visible(AnsweringWithEverything(model=Loan), auditor) == pks(*loans.values())


class AnsweringWrongly(ScopedQuerySet[Loan]):
    def scope_for_customer(self, user: User) -> object:
        return Person.objects.all()

    def scope_for_officer(self, user: User) -> object:
        return 'everything'


def test_a_hook_answering_with_another_models_rows_is_an_error(
    people: dict[str, Person],
) -> None:
    with pytest.raises(TypeError, match='rows of Person, not Loan'):
        AnsweringWrongly(model=Loan).visible_to(people['ana'])


def test_a_hook_answering_with_anything_else_is_an_error(people: dict[str, Person]) -> None:
    with pytest.raises(TypeError, match='answered with str'):
        AnsweringWrongly(model=Loan).visible_to(people['officer'])


# ---------------------------------------------------------------- what it costs


def test_scoping_costs_no_query_of_its_own(
    people: dict[str, Person],
    loans: dict[str, Loan],
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    with django_assert_num_queries(1):
        list(Loan.objects.visible_to(people['ana']))


@SEVERAL_ROLES
def test_several_roles_still_cost_one_query(
    make_user: MakeUser,
    loans: dict[str, Loan],
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    person = make_user(role='officer', extra_roles=['customer', 'auditor'])

    with django_assert_num_queries(1):
        list(AnsweringWithQuerysets(model=Loan).visible_to(person))


# ---------------------------------------------------------------- the ready-made scopes


def test_reference_data_is_reached_by_anybody_signed_in(
    make_user: MakeUser, anonymous: AnonymousUser, loans: dict[str, Loan]
) -> None:
    everything = SignedInReadQuerySet(model=Loan)

    assert visible(everything, make_user()) == pks(*loans.values())
    assert visible(everything, anonymous) == set()
    assert visible(everything, make_user(active=False)) == set()


class OwnedLoans(OwnedQuerySet[Loan]):
    owner_path = 'applicant'


def test_owned_rows_are_reached_by_their_owner(
    people: dict[str, Person], make_user: MakeUser, loans: dict[str, Loan]
) -> None:
    owned = OwnedLoans(model=Loan)

    assert visible(owned, people['bob']) == pks(loans['bob'])
    assert visible(owned, make_user(role='auditor')) == set()
    assert visible(owned, make_user(role='admin')) == pks(*loans.values())
