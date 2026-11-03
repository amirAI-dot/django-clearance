"""
A project configured wrongly is told so by manage.py check, before anybody signs in.

If these fail, a misspelled role silently denies everybody, a misspelled
setting is ignored, or a view that shows every row starts without complaint.
"""

from typing import Any

import pytest
from django.core.checks import CheckMessage
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import include, path
from django.views.generic import DetailView, ListView, UpdateView

from clearance import checks
from clearance.checks import (
    check_scope_hooks,
    check_views,
    scope_hook_errors,
    scoped_querysets,
    settings_errors,
    view_errors,
)
from clearance.conf import clearance_settings
from clearance.protocols import User
from clearance.querysets import ScopedQuerySet
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan
from tests.project.lending.policies import loan_access
from tests.project.lending.querysets import LoanQuerySet


def ids(messages: list[CheckMessage]) -> list[str | None]:
    return [message.id for message in messages]


# ---------------------------------------------------------------- the setting


@override_settings(CLEARANCE={'ROLES': ['admin'], 'EVERY_ROWS_ROLES': ['admin']})
def test_a_misspelled_key_is_refused_not_ignored() -> None:
    errors = settings_errors(rows_are_scoped=True)

    assert ids(errors) == ['clearance.E011']
    assert 'EVERY_ROWS_ROLES' in errors[0].msg


@override_settings(CLEARANCE=['admin'])
def test_a_setting_that_is_not_a_dictionary_is_refused() -> None:
    assert ids(settings_errors(rows_are_scoped=False)) == ['clearance.E011']


@override_settings(CLEARANCE={})
def test_roles_are_required_once_something_scopes_rows() -> None:
    assert ids(settings_errors(rows_are_scoped=True)) == ['clearance.E001']
    assert ids(settings_errors(rows_are_scoped=False)) == []


@pytest.mark.parametrize(
    'roles',
    [
        ['admin', 'loan officer'],
        ['admin', 'admin'],
        [],
        'not.a.module.Role',
        'admin',
        5,
    ],
)
def test_roles_that_cannot_name_hooks_are_refused(roles: object) -> None:
    with override_settings(CLEARANCE={'ROLES': roles}):
        assert ids(settings_errors(rows_are_scoped=False)) == ['clearance.E001']


@override_settings(CLEARANCE={'ROLES': 'tests.project.lending.roles.Role'})
def test_roles_may_be_named_by_a_choices_class() -> None:
    assert clearance_settings.roles == ('admin', 'officer')


@pytest.mark.parametrize('every_row_roles', [['root'], 'admin'])
def test_every_row_roles_must_be_a_list_of_declared_roles(every_row_roles: object) -> None:
    with override_settings(CLEARANCE={'ROLES': ['admin'], 'EVERY_ROW_ROLES': every_row_roles}):
        assert ids(settings_errors(rows_are_scoped=True)) == ['clearance.E005']


@pytest.mark.parametrize(
    'setting',
    [
        {'ROLE_RESOLVER': 'not.a.module.Resolver'},
        {'ROLE_RESOLVER': 'tests.project.lending.models.Loan'},
        {'ROLE_ATTRIBUTE': 'two words'},
    ],
)
def test_a_resolver_that_cannot_be_used_is_refused(setting: dict[str, object]) -> None:
    with override_settings(CLEARANCE={'ROLES': ['admin'], **setting}):
        assert ids(settings_errors(rows_are_scoped=True)) == ['clearance.E010']


@override_settings(CLEARANCE={'ROLES': ['admin'], 'EVERY_ROW_ROLES': ['root']})
def test_using_a_bad_setting_raises_rather_than_guessing() -> None:
    with pytest.raises(ImproperlyConfigured, match='root'):
        _ = clearance_settings.every_row_roles


# ---------------------------------------------------------------- scope hooks


class MisspelledHook(ScopedQuerySet[Loan]):
    def scope_for_offcier(self, user: User) -> None:
        return None


def test_a_hook_for_a_role_nobody_declared_is_reported() -> None:
    errors = scope_hook_errors([MisspelledHook], ['officer', 'customer'])

    assert ids(errors) == ['clearance.E002']
    assert 'scope_for_offcier' in errors[0].msg


def test_hooks_for_declared_roles_pass() -> None:
    assert scope_hook_errors([LoanQuerySet], ['officer', 'customer']) == []


def test_the_querysets_checked_are_the_ones_models_use() -> None:
    assert LoanQuerySet in scoped_querysets()
    assert MisspelledHook not in scoped_querysets()


def test_a_project_scoping_no_rows_has_no_hooks_to_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checks, 'scoped_querysets', list)

    assert check_scope_hooks() == []


@override_settings(CLEARANCE={})
def test_hooks_are_not_checked_against_roles_that_are_missing() -> None:
    assert check_scope_hooks() == [], 'E001 reports the missing roles, once'


# ---------------------------------------------------------------- views


class ScopedOverPeople(ScopedQuerySetMixin, ListView):  # type: ignore[type-arg]
    model = Person


class ScopedOverLoans(ScopedQuerySetMixin, DetailView):  # type: ignore[type-arg]
    model = Loan


class NoPolicy(PolicyRequiredMixin, UpdateView):  # type: ignore[type-arg]
    model = Loan


class UnknownAction(PolicyRequiredMixin, ListView):  # type: ignore[type-arg]
    policy = loan_access.policy
    policy_action = 'aprove'
    model = Loan


def test_a_scoped_view_over_an_unscoped_model_is_reported() -> None:
    assert ids(view_errors([ScopedOverPeople])) == ['clearance.E004']


def test_a_scoped_view_over_a_scoped_model_passes() -> None:
    assert view_errors([ScopedOverLoans]) == []


def test_the_views_checked_are_found_through_every_include() -> None:
    from tests.project.lending import views

    with override_settings(ROOT_URLCONF='tests.test_misconfiguration_fails_at_start_up'):
        assert ids(check_views()) == ['clearance.E004', 'clearance.E009']

    assert issubclass(views.LoanListView, PolicyRequiredMixin)
    assert check_views() == [], 'the project itself is configured right'


@override_settings(ROOT_URLCONF='not.a.module')
def test_a_urlconf_that_does_not_import_is_left_to_django() -> None:
    assert check_views() == []


@pytest.mark.parametrize(
    ('view', 'expected'),
    [(NoPolicy, 'names no policy'), (UnknownAction, 'can_aprove')],
)
def test_a_view_that_cannot_ask_its_policy_is_reported(view: Any, expected: str) -> None:
    errors = view_errors([view])

    assert ids(errors) == ['clearance.E009']
    assert expected in errors[0].msg


#: A URLconf for the test above: two broken views, one behind an include.
urlpatterns = [
    path('people/', ScopedOverPeople.as_view()),
    path('more/', include([path('loans/', NoPolicy.as_view())])),
]
