"""
A person has the roles the project gives them, read from wherever it keeps them.

If these fail, somebody signed out is treated as having a role, a role the
project never declared grants something, or a page asking about roles twenty
times reads them twenty times.
"""

import logging
from collections.abc import Iterable

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from clearance import resolvers
from clearance.protocols import User
from clearance.resolvers import RoleResolver, forget_roles, has_role, reaches_every_row, roles_of
from tests.conftest import MakeUser

SEVERAL_ROLES = override_settings(
    CLEARANCE={'ROLES': ['admin', 'officer', 'customer', 'auditor'], 'ROLE_ATTRIBUTE': 'roles'}
)


class EveryoneIsAnAuditor(RoleResolver):
    def roles_of(self, user: User) -> Iterable[str]:
        return ('auditor',)


def test_the_role_column_is_read_by_default(make_user: MakeUser) -> None:
    assert roles_of(make_user(role='officer')) == {'officer'}


def test_an_empty_role_is_no_role(make_user: MakeUser) -> None:
    assert roles_of(make_user()) == frozenset()


def test_somebody_signed_out_has_no_roles(anonymous: AnonymousUser) -> None:
    assert roles_of(anonymous) == frozenset()


@SEVERAL_ROLES
def test_a_person_may_have_several_roles(make_user: MakeUser) -> None:
    assert roles_of(make_user(role='officer', extra_roles=['customer'])) == {'officer', 'customer'}


def test_a_role_nobody_declared_counts_for_nothing_and_is_reported_once(
    make_user: MakeUser, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(resolvers, '_reported', set())

    with caplog.at_level(logging.WARNING, logger='clearance'):
        assert roles_of(make_user(role='wizard')) == frozenset()
        assert roles_of(make_user(role='wizard')) == frozenset()

    assert [record.getMessage() for record in caplog.records].count(
        'Role \'wizard\' is not in CLEARANCE["ROLES"], so it counts for nothing. '
        'Declare it, or stop giving it to people.'
    ) == 1


def test_the_roles_are_read_once_per_person(make_user: MakeUser) -> None:
    person = make_user(role='officer')

    assert roles_of(person) == {'officer'}
    person.role = 'customer'
    assert roles_of(person) == {'officer'}, 'kept for the rest of the request'

    forget_roles(person)
    assert roles_of(person) == {'customer'}


def test_forgetting_roles_nobody_read_is_harmless(make_user: MakeUser) -> None:
    person = make_user(role='officer')

    forget_roles(person)
    assert roles_of(person) == {'officer'}


def test_a_resolver_keeps_roles_outside_rows_unless_it_says_so(make_user: MakeUser) -> None:
    assert EveryoneIsAnAuditor().roles_subquery(make_user()) is None


@override_settings(
    CLEARANCE={
        'ROLES': ['auditor'],
        'ROLE_RESOLVER': 'tests.test_a_person_has_the_roles_they_are_given.EveryoneIsAnAuditor',
    }
)
def test_a_project_reads_roles_with_its_own_resolver(make_user: MakeUser) -> None:
    assert roles_of(make_user()) == {'auditor'}


@override_settings(CLEARANCE={'ROLES': ['admin'], 'ROLE_ATTRIBUTE': 'pk'})
def test_an_attribute_holding_neither_a_code_nor_a_list_is_an_error(make_user: MakeUser) -> None:
    with pytest.raises(ImproperlyConfigured, match=r'user\.pk holds int'):
        roles_of(make_user())


# ---------------------------------------------------------------- asking about roles


@SEVERAL_ROLES
def test_has_role_means_any_of_them(make_user: MakeUser) -> None:
    person = make_user(role='officer', extra_roles=['customer'])

    assert has_role(person, 'customer')
    assert has_role(person, 'admin', 'officer')
    assert not has_role(person, 'admin', 'auditor')


def test_a_switched_off_account_has_no_role_that_counts(make_user: MakeUser) -> None:
    assert not has_role(make_user(role='officer', active=False), 'officer')


def test_the_superuser_and_every_row_roles_reach_every_row(
    make_user: MakeUser, anonymous: AnonymousUser
) -> None:
    assert reaches_every_row(make_user(superuser=True))
    assert reaches_every_row(make_user(role='admin'))
    assert not reaches_every_row(make_user(role='officer'))
    assert not reaches_every_row(make_user(role='admin', active=False))
    assert not reaches_every_row(anonymous)
