"""
A page built on Django's own views asks the policy, and shows only reachable rows.

If these fail, a project on templates and forms gives up what an API project
has: a list shows every loan, somebody else's loan opens by its address, an
officer approves their own loan, or a view nobody configured lets everybody
in.
"""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.views.generic import ListView, TemplateView

from clearance.decorators import policy_required
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan
from tests.project.lending.policies import LoanPolicy, loan_access

VIEW = 'lending.loan_view'


@pytest.fixture
def ana(make_user: MakeUser) -> Person:
    return make_user(VIEW, 'lending.loan_create', role='customer')


@pytest.fixture
def officer(make_user: MakeUser) -> Person:
    return make_user(VIEW, 'lending.loan_approve', role='officer')


@pytest.fixture
def anas_loan(ana: Person, officer: Person) -> Loan:
    return Loan.objects.create(applicant=ana, officer=officer, amount=100)


def signed_in(client: Client, person: Person) -> Client:
    client.force_login(person)
    return client


# ---------------------------------------------------------------- the list


def test_the_list_sends_somebody_signed_out_to_log_in(client: Client, db: None) -> None:
    response = client.get('/loans/')

    assert response.status_code == 302
    assert response['Location'].startswith('/accounts/login/')


def test_the_list_refuses_somebody_without_the_permission(
    client: Client, make_user: MakeUser
) -> None:
    assert signed_in(client, make_user(role='customer')).get('/loans/').status_code == 403


def test_the_list_shows_only_reachable_rows(
    client: Client, ana: Person, anas_loan: Loan, make_user: MakeUser
) -> None:
    other = Loan.objects.create(applicant=make_user(), amount=200)
    response = signed_in(client, ana).get('/loans/')

    assert response.status_code == 200
    assert f'loan:{anas_loan.pk}' in response.text
    assert f'loan:{other.pk}' not in response.text


# ---------------------------------------------------------------- one row


def test_a_row_out_of_reach_does_not_exist(
    client: Client, anas_loan: Loan, make_user: MakeUser
) -> None:
    stranger = make_user(VIEW, role='customer')

    assert signed_in(client, stranger).get(f'/loans/{anas_loan.pk}/').status_code == 404


def test_a_row_within_reach_opens(client: Client, ana: Person, anas_loan: Loan) -> None:
    assert signed_in(client, ana).get(f'/loans/{anas_loan.pk}/').status_code == 200


def test_the_object_is_judged_once_it_is_found(
    client: Client, officer: Person, make_user: MakeUser
) -> None:
    own = Loan.objects.create(applicant=officer, officer=officer, amount=100)
    other = Loan.objects.create(applicant=make_user(), officer=officer, amount=100)
    officer_client = signed_in(client, officer)

    assert officer_client.get(f'/loans/{own.pk}/approve/').status_code == 403
    assert officer_client.get(f'/loans/{other.pk}/approve/').status_code == 200


def test_a_custom_action_needs_its_own_permission(client: Client, anas_loan: Loan) -> None:
    officer = anas_loan.officer
    assert officer is not None
    officer.user_permissions.clear()

    assert signed_in(client, officer).get(f'/loans/{anas_loan.pk}/approve/').status_code == 403


def test_approving_through_the_form_changes_the_loan(
    client: Client, officer: Person, anas_loan: Loan
) -> None:
    response = signed_in(client, officer).post(
        f'/loans/{anas_loan.pk}/approve/', {'approved': 'on'}
    )

    assert response.status_code == 302
    anas_loan.refresh_from_db()
    assert anas_loan.approved


# ---------------------------------------------------------------- a function view


def test_a_function_view_sends_somebody_signed_out_to_log_in(client: Client, db: None) -> None:
    response = client.get('/loans/apply/')

    assert response.status_code == 302
    assert response['Location'].startswith('/accounts/login/?next=/loans/apply/')


def test_a_function_view_refuses_somebody_without_the_permission(
    client: Client, make_user: MakeUser
) -> None:
    assert signed_in(client, make_user(role='customer')).get('/loans/apply/').status_code == 403


def test_a_function_view_runs_for_somebody_allowed(client: Client, ana: Person) -> None:
    response = signed_in(client, ana).get('/loans/apply/')

    assert response.status_code == 200
    assert response.text == 'applied'


def test_decorating_with_an_action_the_policy_has_no_hook_for_fails_at_once() -> None:
    with pytest.raises(ImproperlyConfigured, match='can_aprove'):
        policy_required(LoanPolicy(), 'aprove')


def test_an_async_view_is_refused_rather_than_left_unguarded() -> None:
    async def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse()

    with pytest.raises(ImproperlyConfigured, match='async'):
        policy_required(LoanPolicy(), 'create')(view)


# ---------------------------------------------------------------- misconfigured views


class Unnamed(PolicyRequiredMixin, TemplateView):
    policy = loan_access.policy


class Policyless(PolicyRequiredMixin, ListView):  # type: ignore[type-arg]
    queryset = Loan.objects.all()


class Unscoped(ScopedQuerySetMixin, ListView):  # type: ignore[type-arg]
    queryset = Person.objects.all()


def test_a_view_with_no_action_to_read_is_refused_not_let_through(
    rf: RequestFactory, ana: Person
) -> None:
    request = rf.get('/')
    request.user = ana

    with pytest.raises(ImproperlyConfigured, match='names no policy_action'):
        Unnamed.as_view()(request)


def test_a_view_with_no_policy_is_refused(rf: RequestFactory, ana: Person) -> None:
    request = rf.get('/')
    request.user = ana

    with pytest.raises(ImproperlyConfigured, match='names no policy'):
        Policyless.as_view()(request)


def test_a_scoped_view_over_an_unscoped_queryset_is_refused(
    rf: RequestFactory, ana: Person
) -> None:
    request = rf.get('/')
    request.user = ana

    with pytest.raises(ImproperlyConfigured, match='shows every row to everybody'):
        Unscoped.as_view()(request)


@pytest.mark.parametrize(
    ('view', 'action'),
    [
        ('LoanListView', 'list'),
        ('LoanDetailView', 'view'),
        ('LoanApproveView', 'approve'),
    ],
)
def test_the_action_is_read_off_the_view_unless_named(view: str, action: str) -> None:
    from tests.project.lending import views

    assert getattr(views, view).resolved_action() == action
