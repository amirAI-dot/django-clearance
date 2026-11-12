"""
An API built on DRF asks the policy, shows only the rows and fields the person
may see, and refuses what they may not write - whatever serializer it uses.

If these fail, a customer reads every loan through the API, reads a credit
score kept for officers, approves their own loan by sending "approved", or a
serializer written without the library writes a protected field - while the
same person is refused all of it on the Django pages.
"""

import subprocess
import sys
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.urls import path
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from clearance.discovery import default_finders, find_actions
from clearance.drf.checks import api_view_errors, check_api_views
from clearance.drf.discovery import APIViewFinder, guarding_policy
from clearance.drf.permissions import ModelPolicyPermission, PolicyPermission, _items
from clearance.drf.serializers import ProtectedFieldsSerializerMixin, protected_serializer
from clearance.drf.viewsets import ScopedReadOnlyViewSet
from clearance.models import ProtectedField
from clearance.policies import BasePolicy
from clearance.services import AccessService
from clearance.writes import refused_writes
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.api import LoanSerializer, PaymentSerializer
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

READER = ('lending.loan_view', 'all')
EDITOR = (READER, ('lending.loan_edit', 'all'))
SCORE = ('lending.loan_view_credit_score', 'lending.loan_edit_credit_score')


@pytest.fixture
def api() -> APIClient:
    return APIClient()


def signed_in(api: APIClient, person: Person) -> APIClient:
    api.force_authenticate(person)
    return api


@pytest.fixture
def ana(make_user: MakeUser) -> Person:
    """A customer: reads her own loans, and applies."""
    return make_user(('lending.loan_view', 'own'), ('lending.loan_create', 'own'))


@pytest.fixture
def loan(ana: Person) -> Loan:
    return Loan.objects.create(applicant=ana, amount=100, credit_score=600)


# ---------------------------------------------------------------- the policy, by action


def test_somebody_signed_out_is_refused(api: APIClient, loan: Loan) -> None:
    assert api.get('/api/loans/').status_code in (401, 403)


def test_a_list_needs_the_permission_and_shows_only_the_rows_reached(
    api: APIClient, make_user: MakeUser, ana: Person, loan: Loan
) -> None:
    Loan.objects.create(applicant=make_user(), amount=1)

    assert signed_in(api, make_user()).get('/api/loans/').status_code == 403
    rows = signed_in(api, ana).get('/api/loans/').json()
    assert [row['id'] for row in rows] == [loan.pk]


def test_somebody_elses_row_does_not_exist(api: APIClient, make_user: MakeUser, loan: Loan) -> None:
    other = make_user(('lending.loan_view', 'own'))

    assert signed_in(api, other).get(f'/api/loans/{loan.pk}/').status_code == 404


def test_creating_needs_its_permission(api: APIClient, make_user: MakeUser, ana: Person) -> None:
    sent = {'amount': 50, 'region': 'north'}

    assert signed_in(api, make_user()).post('/api/loans/', sent).status_code == 403
    created = signed_in(api, ana).post('/api/loans/', sent)
    assert created.status_code == 201
    assert Loan.objects.get(pk=created.json()['id']).applicant == ana


def test_editing_and_deleting_need_theirs_within_their_scope(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    reader = make_user(READER)
    assert signed_in(api, reader).patch(f'/api/loans/{loan.pk}/', {'amount': 1}).status_code == 403

    editor = make_user(*EDITOR)
    assert signed_in(api, editor).patch(f'/api/loans/{loan.pk}/', {'amount': 1}).status_code == 200
    assert signed_in(api, editor).delete(f'/api/loans/{loan.pk}/').status_code == 403

    remover = make_user(READER, ('lending.loan_delete', 'all'))
    assert signed_in(api, remover).delete(f'/api/loans/{loan.pk}/').status_code == 204


def test_an_action_on_a_viewset_needs_its_own_permission(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    address = f'/api/loans/{loan.pk}/remind/'

    assert signed_in(api, make_user(READER)).post(address).status_code == 403
    reminded = signed_in(api, make_user(('lending.loan_remind', 'all'))).post(address)
    assert reminded.json() == {'reminded': loan.pk}


def test_a_view_naming_its_policy_and_action_asks_them(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    assert signed_in(api, make_user(READER)).get('/api/report/').status_code == 403
    report = signed_in(api, make_user(READER, 'lending.loan_report')).get('/api/report/')
    assert report.json() == {'loans': 1}


def test_a_method_nobody_maps_to_an_action_is_refused(api: APIClient, make_user: MakeUser) -> None:
    person = make_user(('lending.view_payment', 'all'))

    assert signed_in(api, person).generic('TRACE', '/api/payments/').status_code == 403


# ---------------------------------------------------------------- fields


def test_a_field_that_may_not_be_read_is_not_in_the_answer(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    hidden = signed_in(api, make_user(READER)).get(f'/api/loans/{loan.pk}/').json()
    shown = signed_in(api, make_user(READER, SCORE[0])).get(f'/api/loans/{loan.pk}/').json()

    assert 'credit_score' not in hidden
    assert shown['credit_score'] == 600


@pytest.mark.parametrize('held', [(), (SCORE[0],)], ids=['not read', 'read, not written'])
def test_a_field_that_may_not_be_written_is_refused_naming_it(
    api: APIClient, make_user: MakeUser, loan: Loan, held: tuple[str, ...]
) -> None:
    response = signed_in(api, make_user(*EDITOR, *held)).patch(
        f'/api/loans/{loan.pk}/', {'credit_score': 900}
    )

    assert response.status_code == 400
    assert response.json() == {'credit_score': ['You may not write credit_score.']}
    loan.refresh_from_db()
    assert loan.credit_score == 600


def test_a_field_written_by_whoever_may_is_saved(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    response = signed_in(api, make_user(*EDITOR, *SCORE)).patch(
        f'/api/loans/{loan.pk}/', {'credit_score': 900}
    )

    assert response.status_code == 200
    loan.refresh_from_db()
    assert loan.credit_score == 900


def test_a_field_marked_in_the_database_is_guarded_on_a_serializer_of_any_kind(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    AccessService(actor=None).protect_field(Payment, 'amount')
    Payment.objects.create(loan=loan, amount=10)
    clerk = make_user(('lending.view_payment', 'all'), 'lending.add_payment')

    assert 'amount' not in signed_in(api, clerk).get('/api/payments/').json()[0]
    refused = signed_in(api, clerk).post(
        '/api/payments/', [{'loan': loan.pk, 'amount': 5}], format='json'
    )
    assert refused.json() == {'amount': ['You may not write amount.']}


# ---------------------------------------------------------------- status values


def test_a_status_value_is_refused_to_whoever_may_not_set_it(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    address = f'/api/loans/{loan.pk}/'

    refused = signed_in(api, make_user(*EDITOR)).patch(address, {'status': 'approved'})
    assert refused.json() == {'status': ['You may not set status to approved.']}

    approver = make_user(*EDITOR, ('lending.loan_approve', 'all'))
    assert signed_in(api, approver).patch(address, {'status': 'approved'}).status_code == 200


def test_a_new_row_cannot_be_born_with_a_status_nobody_gave(api: APIClient, ana: Person) -> None:
    response = signed_in(api, ana).post('/api/loans/', {'amount': 5, 'status': 'approved'})

    assert response.status_code == 400
    assert 'status' in response.json()


# ---------------------------------------------------------------- a serializer on its own


def test_a_serializer_outside_a_view_is_told_whose_it_is(make_user: MakeUser, loan: Loan) -> None:
    protected = protected_serializer(LoanSerializer)

    shown = protected(loan, context={'user': make_user(SCORE[0])}).data
    assert shown['credit_score'] == 600

    with pytest.raises(ImproperlyConfigured, match='whose fields to show'):
        protected(loan).data  # noqa: B018


def test_a_serializer_refuses_what_it_may_not_write_on_its_own(
    make_user: MakeUser, loan: Loan
) -> None:
    serializer = PaymentSerializer(
        data={'loan': loan.pk, 'amount': 1, 'state': 'refunded'}, context={'user': make_user()}
    )
    AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded']
    )

    assert not serializer.is_valid()
    assert serializer.errors == {'state': ['You may not set state to refunded.']}

    assert not PaymentSerializer(
        data=['not', 'an', 'object'], context={'user': make_user()}
    ).is_valid()


def test_the_mixin_needs_a_model() -> None:
    class Plain(ProtectedFieldsSerializerMixin, serializers.Serializer):  # type: ignore[type-arg]
        name = serializers.CharField()

    with pytest.raises(ImproperlyConfigured, match='use it on a ModelSerializer'):
        Plain(context={'user': None}).fields  # noqa: B018


def test_a_serializer_is_protected_once_and_only_when_it_can_be() -> None:
    class Plain(serializers.Serializer):  # type: ignore[type-arg]
        pass

    assert protected_serializer(LoanSerializer) is protected_serializer(LoanSerializer)
    assert issubclass(protected_serializer(LoanSerializer), ProtectedFieldsSerializerMixin)
    assert protected_serializer(PaymentSerializer) is PaymentSerializer
    assert protected_serializer(Plain) is Plain


# ---------------------------------------------------------------- the permission classes


class Nameless(APIView):
    permission_classes = (PolicyPermission,)


class Modelless(generics.ListAPIView):  # type: ignore[type-arg]
    permission_classes = (ModelPolicyPermission,)


class FindsItsModel(generics.ListAPIView):  # type: ignore[type-arg]
    permission_classes = (ModelPolicyPermission,)
    serializer_class = PaymentSerializer

    def get_queryset(self) -> Any:
        return Payment.objects.all()


class ShowsEverything(generics.ListAPIView):  # type: ignore[type-arg]
    permission_classes = (ModelPolicyPermission,)
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer


class LoansToRead(ScopedReadOnlyViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer


#: A URLconf for the tests below.
urlpatterns = [
    path('nameless/', Nameless.as_view()),
    path('modelless/', Modelless.as_view()),
    path('finds/', FindsItsModel.as_view()),
    path('everything/', ShowsEverything.as_view()),
]


@pytest.mark.parametrize('view', [Nameless, Modelless])
def test_a_view_with_no_policy_to_ask_fails_loudly(make_user: MakeUser, view: Any) -> None:
    request = APIRequestFactory().get('/')
    request.user = make_user()  # type: ignore[attr-defined]

    with pytest.raises(ImproperlyConfigured, match=r'policy to ask|no queryset'):
        view.as_view()(request)


def test_a_view_finding_its_model_by_its_own_queryset_asks_its_policy(
    api: APIClient, make_user: MakeUser
) -> None:
    with override_settings(
        ROOT_URLCONF='tests.test_an_api_asks_the_policy_and_guards_what_is_written'
    ):
        assert signed_in(api, make_user()).get('/finds/').status_code == 403
        assert signed_in(api, make_user('lending.view_payment')).get('/finds/').status_code == 200


def test_a_read_only_viewset_protects_its_serializer(make_user: MakeUser, loan: Loan) -> None:
    view = LoansToRead()

    assert issubclass(view.get_serializer_class(), ProtectedFieldsSerializerMixin)


# ---------------------------------------------------------------- at start-up


def test_a_view_that_cannot_ask_or_would_show_every_field_is_reported() -> None:
    errors = api_view_errors([Nameless, Modelless, FindsItsModel, ShowsEverything, LoansToRead])

    assert [(error.obj, error.id) for error in errors] == [
        (Nameless, 'clearance.E009'),
        (Modelless, 'clearance.E009'),
        (ShowsEverything, 'clearance.E003'),
    ]


def test_the_api_views_checked_are_the_urlconfs() -> None:
    with override_settings(
        ROOT_URLCONF='tests.test_an_api_asks_the_policy_and_guards_what_is_written'
    ):
        assert [error.id for error in check_api_views()] == [
            'clearance.E009',
            'clearance.E009',
            'clearance.E003',
        ]

    assert check_api_views() == [], 'the project itself is configured right'

    with override_settings(ROOT_URLCONF='not.a.module'):
        assert check_api_views() == [], "Django's own check reports it"


# ---------------------------------------------------------------- actions found


def test_an_action_of_a_viewset_and_one_named_on_an_api_view_are_found() -> None:
    found = {(action.permission, action.origin) for action in APIViewFinder().find()}

    assert ('lending.loan_remind', 'tests.project.lending.api.LoanViewSet') in found
    assert ('lending.loan_report', 'tests.project.lending.api.LoanReport') in found
    assert {action.permission for action in find_actions()} >= {
        'lending.loan_remind',
        'lending.loan_report',
    }


def test_a_view_with_no_policy_to_ask_has_nothing_to_find() -> None:
    with override_settings(
        ROOT_URLCONF='tests.test_an_api_asks_the_policy_and_guards_what_is_written'
    ):
        assert {action.origin.rsplit('.', 1)[1] for action in APIViewFinder().find()} <= {
            'FindsItsModel',
            'ShowsEverything',
        }


def test_without_drf_its_views_are_not_searched(monkeypatch: pytest.MonkeyPatch) -> None:
    from django.apps import apps

    monkeypatch.setattr(apps, 'is_installed', lambda name: name != 'rest_framework')

    assert 'APIViewFinder' not in [type(finder).__name__ for finder in default_finders()]


def test_the_library_works_with_drf_not_installed_at_all() -> None:
    script = """
import sys
sys.modules['rest_framework'] = None   # as if it were never installed
import django
from django.conf import settings
settings.configure(
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'clearance'],
    DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
    AUTHENTICATION_BACKENDS=['clearance.backends.ClearanceBackend'],
)
django.setup()
import clearance.actions, clearance.checks, clearance.discovery, clearance.fields
import clearance.forms, clearance.services, clearance.views, clearance.writes
from clearance.discovery import default_finders
assert [type(f).__name__ for f in default_finders()] == ['ViewFinder']
print('ok')
"""
    done = subprocess.run(
        [sys.executable, '-c', script], capture_output=True, text=True, check=False
    )

    assert done.stdout.strip() == 'ok', done.stderr


def test_a_field_protected_later_is_left_out_by_a_viewset_nobody_changed(
    api: APIClient, make_user: MakeUser, loan: Loan
) -> None:
    ProtectedField.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), field='region'
    )

    assert 'region' not in signed_in(api, make_user(READER)).get(f'/api/loans/{loan.pk}/').json()


# ---------------------------------------------------------------- the edges


class LedgerPolicy(BasePolicy):
    """A resource that is not one model."""

    app_label = 'lending'
    codename = 'ledger'


LedgerPolicy.check_declaration()


def test_an_object_outside_what_the_policy_allows_is_refused(
    make_user: MakeUser, loan: Loan
) -> None:
    request = Request(APIRequestFactory().get('/'))
    request.user = make_user(('lending.loan_view', 'own'))  # not the applicant
    view = LoansToRead(action='retrieve', request=request)

    assert not ModelPolicyPermission().has_object_permission(request, view, loan)


def test_a_policy_of_no_model_has_no_fields_to_guard(make_user: MakeUser) -> None:
    request = Request(APIRequestFactory().post('/', {'amount': 1}, format='json'))
    request.user = make_user()

    assert PolicyPermission.refuse_writes(request, LedgerPolicy(), None) is None


def test_a_body_that_is_neither_an_object_nor_a_list_has_no_fields() -> None:
    assert list(_items('just text')) == []


def test_values_that_are_no_field_of_the_model_are_not_this_libraries_to_judge(
    make_user: MakeUser,
) -> None:
    assert refused_writes(make_user(), Loan, {'note': 'anything'}) == {}


def test_a_serializer_of_a_model_with_nothing_protected_shows_every_field(
    make_user: MakeUser, loan: Loan
) -> None:
    payment = Payment.objects.create(loan=loan, amount=10)

    assert set(PaymentSerializer(payment, context={'user': make_user()}).data) == {
        'id',
        'loan',
        'amount',
        'state',
    }


def test_only_a_view_that_asks_a_policy_has_one_to_ask() -> None:
    class Open(APIView):
        permission_classes = (IsAuthenticated,)

    class Guarded(APIView):
        permission_classes = (IsAuthenticated, PolicyPermission)
        policy = LedgerPolicy()

    assert guarding_policy(Open) is None
    assert isinstance(guarding_policy(Guarded), LedgerPolicy)


def test_without_drf_the_app_registers_only_its_own_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.apps import apps
    from django.core import checks

    from clearance.drf.checks import check_api_views

    registered: list[Any] = []
    monkeypatch.setattr(apps, 'is_installed', lambda name: name != 'rest_framework')
    monkeypatch.setattr(checks, 'register', lambda check, *tags: registered.append(check))

    apps.get_app_config('clearance').ready()

    assert registered, 'its own checks'
    assert check_api_views not in registered
