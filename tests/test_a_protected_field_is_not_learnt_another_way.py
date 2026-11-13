"""
A protected field is hidden from every door - and from every way round one.

If these fail, somebody without ``loan_view_credit_score`` still learns the
score: by filtering the admin list from the address bar, through a related
row's serializer, by searching an API, or through a proxy of the model - and
a value a status action claims is written under another name.

Each of these was a finding of the 0.1.0 review.
"""

import sys
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, serializers, viewsets
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from clearance.actions import writable_values
from clearance.drf.permissions import ModelPolicyPermission
from clearance.drf.serializers import protected_serializer
from clearance.drf.viewsets import ScopedModelViewSet
from clearance.fields import readable_fields
from clearance.models import ProtectedField
from clearance.permissions import field_permission
from clearance.writes import refused_writes
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.api import LoanViewSet
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

READER = ('lending.loan_view', 'all')
SCORE_VIEW = 'lending.loan_view_credit_score'
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


def test_an_api_is_not_sorted_by_a_protected_field(make_user: MakeUser) -> None:
    class SortedLoans(LoanViewSet):
        filter_backends = (filters.OrderingFilter,)
        ordering_fields = ('amount', 'credit_score')
        ordering = ('-credit_score',)

    owner = make_user()
    low = Loan.objects.create(applicant=owner, amount=1, credit_score=300)
    high = Loan.objects.create(applicant=owner, amount=2, credit_score=800)
    view = SortedLoans.as_view({'get': 'list'})

    def listed(person: Person, **query: str) -> list[int]:
        request = APIRequestFactory().get('/', query)
        force_authenticate(request, person)
        return [row['id'] for row in view(request).data]

    clerk = make_user(READER)  # may not read the credit score
    officer = make_user(READER, 'lending.loan_view_credit_score')

    assert listed(officer) == [high.pk, low.pk]
    assert listed(officer, ordering='credit_score') == [low.pk, high.pk]
    assert listed(clerk) == listed(clerk, ordering='-credit_score') == [low.pk, high.pk]
    assert listed(clerk, ordering='-amount') == [high.pk, low.pk]


def test_a_related_row_is_not_written_under_the_name_of_its_column(make_user: MakeUser) -> None:
    """``officer_id`` is ``officer``: a field is protected under either name."""
    ProtectedField.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), field='officer'
    )
    clerk = make_user(*EDITOR)

    assert refused_writes(clerk, Loan, {'officer_id': clerk.pk}) == {
        'officer': 'You may not write officer.'
    }


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
        # ... and it is the one field, with the one pair of permissions.
        assert field_permission(RecentLoan, 'credit_score', 'view') == SCORE_VIEW
        assert 'credit_score' in readable_fields(make_user(READER, SCORE_VIEW), RecentLoan)
        assert writable_values(clerk, RecentLoan, 'status') == {'pending'}
    finally:
        del apps.all_models['lending']['recentloan']
        apps.clear_cache()


# ---------------------------------------------------------------------- the permission class alone


class Decided(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Written knowing nothing of the library, with the status under another name."""

    decision = serializers.CharField(source='status')

    class Meta:
        model = Loan
        fields = ('id', 'amount', 'decision')


class PlainLoans(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """No protected serializer - chosen at run time, where E003 cannot see it."""

    permission_classes = (ModelPolicyPermission,)
    queryset = Loan.objects.all()

    def get_serializer_class(self) -> Any:
        return Decided


class NoSerializer(generics.GenericAPIView):  # type: ignore[type-arg]
    permission_classes = (ModelPolicyPermission,)
    queryset = Loan.objects.all()

    def post(self, request: Any) -> Any:
        return Response({})


def test_the_permission_class_refuses_a_value_sent_under_another_name(
    make_user: MakeUser,
) -> None:
    editor = make_user(('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))
    loan = Loan.objects.create(applicant=editor, amount=1)
    request = APIRequestFactory().patch('/', {'decision': 'approved'}, format='json')
    force_authenticate(request, editor)

    response = PlainLoans.as_view({'patch': 'partial_update'})(request, pk=loan.pk)

    loan.refresh_from_db()
    assert response.status_code == 400
    assert 'decision' in response.data
    assert loan.status == 'pending'


def test_a_view_naming_no_serializer_is_asked_by_the_names_sent(make_user: MakeUser) -> None:
    request = APIRequestFactory().post('/', {'amount': 1}, format='json')
    force_authenticate(request, make_user(('lending.loan_create', 'all')))

    assert NoSerializer.as_view()(request).status_code == 200


# ---------------------------------------------------------------------- django-filter


class FilteredLoans(LoanViewSet):
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('status', 'credit_score')


def listed(person: Person, query: str) -> list[int]:
    request = APIRequestFactory().get(f'/?{query}')
    force_authenticate(request, person)
    response = FilteredLoans.as_view({'get': 'list'})(request)
    return sorted(row['id'] for row in response.data)


def test_a_filterset_filters_only_by_the_fields_the_person_may_read(make_user: MakeUser) -> None:
    """``?credit_score=700`` asked whether a score is 700, of somebody who may not read it."""
    owner = make_user()
    scored = Loan.objects.create(applicant=owner, amount=1, credit_score=700, status='approved')
    other = Loan.objects.create(applicant=owner, amount=1, credit_score=500)
    reader = make_user(READER)
    allowed = make_user(READER, SCORE_VIEW)

    assert listed(reader, 'credit_score=700') == sorted([scored.pk, other.pk])
    assert listed(reader, 'status=approved') == [scored.pk]
    assert listed(allowed, 'credit_score=700') == [scored.pk]


def test_without_django_filter_the_library_knows_drfs_own_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clearance.drf.viewsets import _backends

    monkeypatch.setitem(sys.modules, 'django_filters.rest_framework', None)

    assert [base for _mixin, base in _backends()] == [filters.SearchFilter, filters.OrderingFilter]
