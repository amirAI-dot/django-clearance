"""
A project configured wrongly is told so by manage.py check, before anybody signs in.

If these fail, a misspelled scope is offered to an administrator and reaches
nothing, a revocation silently does nothing because the backend is missing
or has company, a model offers permissions nothing checks, or a view that
shows every row starts without complaint.
"""

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from django.core.checks import CheckMessage
from django.db.models import Q
from django.test import override_settings
from django.urls import include, path
from django.views.generic import TemplateView, UpdateView

from clearance.checks import (
    BACKEND,
    MODEL_BACKEND,
    backend_errors,
    check_settings,
    check_views,
    permission_errors,
    scope_errors,
    scoped_querysets,
)
from clearance.permissions import build_permissions
from clearance.protocols import User
from clearance.querysets import ScopedQuerySet
from clearance.views import PolicyRequiredMixin
from tests.project.lending.models import Loan, Payment
from tests.project.lending.querysets import LoanQuerySet, PaymentQuerySet


def ids(messages: list[CheckMessage]) -> list[str | None]:
    return [message.id for message in messages]


# ---------------------------------------------------------------- the setting


@pytest.mark.parametrize(
    'setting',
    [{'SYNC_ON_MIGRAT': True}, ['ACCESS'], {'RULE_DEPTH': 0}, {'RULE_DEPTH': True}],
    ids=['a misspelled key', 'not a dictionary', 'no relations at all', 'not a number'],
)
def test_a_setting_that_cannot_be_read_is_refused_not_ignored(setting: object) -> None:
    with override_settings(CLEARANCE=setting):
        errors = check_settings()

    assert ids(errors) == ['clearance.E011']


def test_a_setting_of_known_keys_passes_and_the_rest_keep_their_defaults() -> None:
    from clearance.conf import clearance_settings

    with override_settings(CLEARANCE={'SYNC_ON_MIGRATE': True, 'RULE_DEPTH': 2}):
        assert check_settings() == []
        assert clearance_settings.value('RULE_DEPTH') == 2
        assert clearance_settings.value('ACCESS') is None


# ---------------------------------------------------------------- the backend


def test_without_the_backend_revocations_and_scopes_would_do_nothing() -> None:
    assert ids(backend_errors([MODEL_BACKEND])) == ['clearance.E006']


def test_djangos_backend_beside_it_would_hand_back_every_revocation() -> None:
    assert ids(backend_errors([BACKEND, MODEL_BACKEND])) == ['clearance.E007']


def test_the_backend_alone_passes() -> None:
    assert backend_errors([BACKEND, 'project.auth.OtherBackend']) == []


# ---------------------------------------------------------------- permissions


class HalfDeclared:
    """
    A model's options as a model forgetting ``default_permissions = ()`` has them.

    A stand-in rather than a model: a model declared here would join the test
    project's app, and every check of the whole project would report it.
    """

    _meta = SimpleNamespace(
        label='lending.HalfDeclared',
        permissions=build_permissions('half', 'halves'),
        default_permissions=('add', 'change', 'delete', 'view'),
    )


def test_a_model_declaring_its_own_permissions_but_keeping_djangos_is_refused() -> None:
    errors = permission_errors([HalfDeclared])  # type: ignore[list-item]

    assert ids(errors) == ['clearance.E014']
    assert 'default_permissions = ()' in (errors[0].hint or '')


def test_a_model_keeping_only_djangos_or_only_its_own_passes() -> None:
    assert permission_errors([Loan, Payment]) == []


# ---------------------------------------------------------------- scopes


class Disagreeing(ScopedQuerySet[Loan]):
    scopes: ClassVar = {'own': 'Own', 'branch': 'Branch'}
    default_scope = 'nowhere'

    def scope_own(self, user: User) -> Q:
        return Q(applicant=user)

    def scope_reviewing(self, user: User) -> Q:
        return Q(officer=user)


class RedefiningAll(ScopedQuerySet[Loan]):
    scopes: ClassVar = {'all': 'Mine, really'}

    def scope_all(self, user: User) -> Q:
        return Q(applicant=user)


def test_scopes_and_their_methods_must_agree() -> None:
    messages = [error.msg for error in scope_errors([Disagreeing])]

    assert messages == [
        "Disagreeing: scopes offers 'branch' with no scope_branch().",
        'Disagreeing: scope_reviewing() is not in scopes, so nobody can choose it.',
        "Disagreeing: default_scope 'nowhere' is not a scope it offers.",
    ]


def test_all_cannot_be_redefined() -> None:
    assert ids(scope_errors([RedefiningAll])) == ['clearance.E002']


def test_the_projects_own_querysets_pass() -> None:
    assert scope_errors([LoanQuerySet, PaymentQuerySet]) == []


def test_the_querysets_checked_are_the_ones_models_use() -> None:
    assert {LoanQuerySet, PaymentQuerySet} <= set(scoped_querysets())
    assert Disagreeing not in scoped_querysets()


# ---------------------------------------------------------------- views


class NoModel(PolicyRequiredMixin, TemplateView):
    policy_action = 'view'


class UnnameableAction(PolicyRequiredMixin, UpdateView):  # type: ignore[type-arg]
    policy_action = 'Approve!'
    model = Loan


@pytest.mark.parametrize(
    ('view', 'expected'),
    [
        (NoModel, 'clearance.E009'),
        (UnnameableAction, 'clearance.E009'),
    ],
)
def test_a_view_that_would_show_every_row_or_cannot_ask_is_reported(
    view: Any, expected: str
) -> None:
    from clearance.checks import view_errors

    assert ids(view_errors([view])) == [expected]


def test_a_view_that_asks_no_policy_is_not_this_checks_business() -> None:
    from clearance.checks import view_errors

    assert view_errors([TemplateView]) == []


def test_the_views_checked_are_found_through_every_include() -> None:
    with override_settings(ROOT_URLCONF='tests.test_misconfiguration_fails_at_start_up'):
        assert ids(check_views()) == ['clearance.E009', 'clearance.E009']

    assert check_views() == [], 'the project itself is configured right'


@override_settings(ROOT_URLCONF='not.a.module')
def test_a_urlconf_that_does_not_import_is_left_to_django() -> None:
    assert check_views() == []


#: A URLconf for the test above: two views that cannot ask, one behind an include.
urlpatterns = [
    path('loans/', UnnameableAction.as_view()),
    path('more/', include([path('nothing/', NoModel.as_view())])),
]
