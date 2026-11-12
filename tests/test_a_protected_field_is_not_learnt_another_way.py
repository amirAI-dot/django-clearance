"""
A protected field is hidden from every door - and from every way round one.

If these fail, somebody without ``loan_view_credit_score`` still learns the
score: by filtering the admin list from the address bar, through a related
row's serializer, by searching an API, or through a proxy of the model - and
a value a status action claims is written under another name.

Each of these is a finding of the 0.1.0 review; each fails until it is fixed.
"""

from typing import Any

import pytest
from django.test import Client
from rest_framework import filters, serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from clearance.drf.serializers import protected_serializer
from clearance.drf.viewsets import ScopedModelViewSet
from clearance.fields import readable_fields
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.api import LoanViewSet
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

READER = ('lending.loan_view', 'all')
EDITOR = (READER, ('lending.loan_edit', 'all'))


def call(view: Any, method: str, person: Person, data: Any = None, **kwargs: Any) -> Any:
    request = getattr(APIRequestFactory(), method)('/', data, format='json')
    force_authenticate(request, person)
    return view(request, **kwargs)


def test_the_admin_list_is_not_filtered_by_a_protected_field_from_the_address_bar(
    make_user: MakeUser,
) -> None:
    """``?credit_score__gte=`` is a yes-or-no question about the score, asked until it is known."""
    Loan.objects.create(applicant=make_user(), amount=100, credit_score=600)
    clerk = make_user(READER)  # may not read the credit score
    Person.objects.filter(pk=clerk.pk).update(is_staff=True)
    client = Client()
    client.force_login(Person.objects.get(pk=clerk.pk))

    def shown(query: str) -> int | None:
        page = client.get(f'/admin/lending/loan/?{query}')
        return page.context['cl'].result_count if page.status_code == 200 else None

    assert shown('credit_score__gte=500') == shown('credit_score__gte=700')


def test_a_related_rows_protected_field_is_left_out_of_a_nested_serializer(
    make_user: MakeUser,
) -> None:
    class PaymentSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
        class Meta:
            model = Payment
            fields = ('id', 'amount', 'loan')
            depth = 1

    loan = Loan.objects.create(applicant=make_user(), amount=100, credit_score=600)
    payment = Payment.objects.create(loan=loan, amount=5)
    clerk = make_user(READER, 'lending.view_payment')  # may not read the credit score

    shown = protected_serializer(PaymentSerializer)(payment, context={'user': clerk}).data

    assert 'credit_score' not in shown['loan']


def test_an_api_is_not_searched_by_a_protected_field(make_user: MakeUser) -> None:
    class SearchedLoans(LoanViewSet):
        filter_backends = (filters.SearchFilter,)
        search_fields = ('region', 'credit_score')

    Loan.objects.create(applicant=make_user(), amount=100, region='north', credit_score=600)
    clerk = make_user(READER)  # may not read the credit score
    view = SearchedLoans.as_view({'get': 'list'})

    def found(search: str) -> int:
        request = APIRequestFactory().get('/', {'search': search})
        force_authenticate(request, clerk)
        return len(view(request).data)

    assert found('600') == found('601') == 0


def test_a_value_a_status_action_claims_is_refused_under_another_name(
    make_user: MakeUser,
) -> None:
    class DecisionSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
        decision = serializers.ChoiceField(source='status', choices=Loan.status.field.choices)

        class Meta:
            model = Loan
            fields = ('id', 'decision')

    class Decisions(ScopedModelViewSet):
        queryset = Loan.objects.all()
        serializer_class = DecisionSerializer

    loan = Loan.objects.create(applicant=make_user(), amount=100)
    clerk = make_user(*EDITOR)  # may edit a loan, may not approve one

    response = call(
        Decisions.as_view({'patch': 'partial_update'}),
        'patch',
        clerk,
        {'decision': 'approved'},
        pk=loan.pk,
    )

    loan.refresh_from_db()
    assert response.status_code == 400
    assert loan.status == 'pending'


def test_a_field_protected_in_code_is_protected_on_a_proxy_of_its_model(
    make_user: MakeUser,
) -> None:
    from django.apps import apps

    class RecentLoan(Loan):
        class Meta:
            proxy = True
            app_label = 'lending'

    try:
        clerk = make_user(READER)  # may not read the credit score

        assert 'credit_score' not in readable_fields(clerk, Loan)
        assert 'credit_score' not in readable_fields(clerk, RecentLoan)
    finally:
        del apps.all_models['lending']['recentloan']
        apps.clear_cache()
