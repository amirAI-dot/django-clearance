"""
A page built on Django's own views asks the policy, and shows only reachable rows.

If these fail, a project on templates and forms gives up what an API project
has: a list shows every loan, somebody else's loan opens by its address, an
officer approves their own loan, a page with no policy named lets everybody
in, or a view nobody configured is let through.
"""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory
from django.views.generic import TemplateView

from clearance.decorators import policy_required
from clearance.views import PolicyRequiredMixin
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment
from tests.project.lending.policies import LoanPolicy, loan_access


@pytest.fixture
def ana(make_user: MakeUser) -> Person:
    """A customer: sees her own loans, applies for more."""
    return make_user(('lending.loan_view', 'own'), 'lending.loan_create')


@pytest.fixture
def officer(make_user: MakeUser) -> Person:
    """An officer: sees and approves the loans they review."""
    return make_user(('lending.loan_view', 'reviewing'), ('lending.loan_approve', 'reviewing'))


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
    assert signed_in(client, make_user()).get('/loans/').status_code == 403


def test_the_list_shows_only_reachable_rows(
    client: Client, ana: Person, anas_loan: Loan, make_user: MakeUser
) -> None:
    other = Loan.objects.create(applicant=make_user(), amount=200)
    response = signed_in(client, ana).get('/loans/')

    assert response.status_code == 200
    assert f'loan:{anas_loan.pk}' in response.text
    assert f'loan:{other.pk}' not in response.text


def test_a_page_naming_no_policy_asks_its_models_own(
    client: Client, ana: Person, make_user: MakeUser
) -> None:
    payer = make_user('lending.view_payment')
    theirs = Payment.objects.create(loan=Loan.objects.create(applicant=payer, amount=1), amount=10)
    Payment.objects.create(loan=Loan.objects.create(applicant=ana, amount=1), amount=20)

    assert signed_in(client, ana).get('/loans/payments/').status_code == 403

    response = signed_in(client, payer).get('/loans/payments/')

    assert response.status_code == 200
    assert response.text.split() == [f'payment:{theirs.pk}'], "Django's name, the default scope"


# ---------------------------------------------------------------- one row


def test_a_row_out_of_reach_does_not_exist(
    client: Client, anas_loan: Loan, make_user: MakeUser
) -> None:
    stranger = make_user(('lending.loan_view', 'own'))

    assert signed_in(client, stranger).get(f'/loans/{anas_loan.pk}/').status_code == 404


def test_a_row_within_reach_opens(client: Client, ana: Person, anas_loan: Loan) -> None:
    assert signed_in(client, ana).get(f'/loans/{anas_loan.pk}/').status_code == 200


def test_the_rows_of_an_action_are_its_own_scopes(
    client: Client, officer: Person, make_user: MakeUser
) -> None:
    reviewed = Loan.objects.create(applicant=make_user(), officer=officer, amount=100)
    elsewhere = Loan.objects.create(applicant=make_user(), amount=100)
    officer_client = signed_in(client, officer)

    assert officer_client.get(f'/loans/{reviewed.pk}/approve/').status_code == 200
    assert officer_client.get(f'/loans/{elsewhere.pk}/approve/').status_code == 404


def test_the_object_is_judged_once_it_is_found(client: Client, officer: Person) -> None:
    own = Loan.objects.create(applicant=officer, officer=officer, amount=100)

    assert signed_in(client, officer).get(f'/loans/{own.pk}/approve/').status_code == 403


def test_a_custom_action_needs_its_own_permission(
    client: Client, make_user: MakeUser, anas_loan: Loan
) -> None:
    viewer = make_user(('lending.loan_view', 'all'))

    assert signed_in(client, viewer).get(f'/loans/{anas_loan.pk}/approve/').status_code == 403


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
    assert signed_in(client, make_user()).get('/loans/apply/').status_code == 403


def test_a_function_view_runs_for_somebody_allowed(client: Client, ana: Person) -> None:
    response = signed_in(client, ana).get('/loans/apply/')

    assert response.status_code == 200
    assert response.text == 'applied'


def test_decorating_with_a_name_that_could_never_be_an_action_fails_at_once() -> None:
    with pytest.raises(ImproperlyConfigured, match="cannot decide 'Approve!'"):
        policy_required(LoanPolicy(), 'Approve!')


def test_an_async_view_is_refused_rather_than_left_unguarded() -> None:
    async def view(request: HttpRequest) -> HttpResponse:
        return HttpResponse()

    with pytest.raises(ImproperlyConfigured, match='async'):
        policy_required(LoanPolicy(), 'create')(view)


# ---------------------------------------------------------------- misconfigured views


class Unnamed(PolicyRequiredMixin, TemplateView):
    policy = loan_access.policy


class Modelless(PolicyRequiredMixin, TemplateView):
    policy_action = 'view'


@pytest.mark.parametrize(
    ('view', 'message'),
    [
        (Unnamed, 'names no policy_action'),
        (Modelless, 'no model whose policy could be asked'),
    ],
)
def test_a_view_that_cannot_be_judged_is_refused_not_let_through(
    rf: RequestFactory, ana: Person, view: type, message: str
) -> None:
    request = rf.get('/')
    request.user = ana

    with pytest.raises(ImproperlyConfigured, match=message):
        view.as_view()(request)  # type: ignore[attr-defined]


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


@pytest.mark.parametrize(
    ('drf_action', 'action'),
    [('retrieve', 'view'), ('partial_update', 'edit'), ('destroy', 'delete'), ('print', 'print')],
)
def test_a_viewsets_action_is_read_in_the_librarys_words(drf_action: str, action: str) -> None:
    from types import SimpleNamespace

    from clearance.views import action_of

    assert action_of(SimpleNamespace(action=drf_action)) == action
