"""
What the review of 0.1.0 fixed, held at the doors its own tests did not reach.

If these fail, a fix holds on one door and not the next: a row added through
an inline is written outside the scope of ``create``, a date list says which
dates a hidden field holds, a second limited role widens a ceiling unasked, a
nested serializer shows a protected field, or a fix made for one shape of a
project - a proxy, a queryset of its own - fails the shape beside it.
"""

from typing import Any

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import modelformset_factory
from django.test import Client, RequestFactory
from rest_framework import serializers

from clearance.admin.options import _reaching, formset_for, protected_admin
from clearance.checks import field_errors
from clearance.drf.serializers import protected_serializer
from clearance.limits import Limits
from clearance.querysets import visible
from clearance.registry import registry
from clearance.roles.models import Role, RoleCeiling
from clearance.roles.services import RoleService
from clearance.safety import AccessRefused
from clearance.services import AccessService
from clearance.translations.services import TranslationService
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.api import PaymentSerializer
from tests.project.lending.models import Loan, Payment, Statement
from tests.project.lending.querysets import LoanQuerySet

pytestmark = pytest.mark.django_db


def staff(person: Person) -> Person:
    Person.objects.filter(pk=person.pk).update(is_staff=True)
    return Person.objects.get(pk=person.pk)


def admin_of(person: Person) -> Client:
    client = Client()
    client.force_login(person)
    return client


def posted(form: Any) -> dict[str, Any]:
    """What a browser would send back for ``form``, unchanged."""
    data = {}

    for name, field in form.fields.items():
        value = form[name].value()
        if field.disabled or value is None or value is False:
            continue
        data[form.add_prefix(name)] = 'on' if value is True else value

    return data


def loan_page(client: Client, loan: Loan) -> dict[str, Any]:
    """The loan's change page as a browser would send it back, with its payments."""
    page = client.get(f'/admin/lending/loan/{loan.pk}/change/')
    data = posted(page.context['adminform'].form)

    for formset in page.context['inline_admin_formsets']:
        data.update(posted(formset.formset.management_form))
        for form in formset.formset.forms:
            data.update(posted(form))
            data.setdefault(form.add_prefix('id'), form.instance.pk)
            data.setdefault(form.add_prefix('loan'), loan.pk)

    return data


# ---------------------------------------------------------------------- the admin site


def test_a_row_added_through_an_inline_stays_within_the_scope_of_create(
    make_user: MakeUser,
) -> None:
    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),
            ('lending.loan_edit', 'all'),
            ('lending.view_payment', 'all'),
            ('lending.add_payment', 'own'),  # a payment only on a loan of their own
        )
    )
    theirs = Loan.objects.create(applicant=make_user(), amount=100)
    client = admin_of(clerk)
    data = loan_page(client, theirs)
    data.update(
        {
            'payments-TOTAL_FORMS': '1',
            'payments-0-loan': theirs.pk,
            'payments-0-amount': '5',
            'payments-0-state': 'due',
        }
    )

    response = client.post(f'/admin/lending/loan/{theirs.pk}/change/', data)

    assert response.status_code == 403
    assert not Payment.objects.exists()


def test_every_row_of_an_inline_the_person_may_edit_is_changed(make_user: MakeUser) -> None:
    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),
            ('lending.loan_edit', 'all'),
            ('lending.view_payment', 'all'),
            ('lending.change_payment', 'own'),
        )
    )
    mine = Loan.objects.create(applicant=clerk, amount=100)
    first, second = (Payment.objects.create(loan=mine, amount=amount) for amount in (1, 2))
    client = admin_of(clerk)
    data = loan_page(client, mine)
    data.update({'payments-0-amount': '10', 'payments-1-amount': '20'})

    client.post(f'/admin/lending/loan/{mine.pk}/change/', data)

    assert sorted(Payment.objects.values_list('amount', flat=True)) == [10, 20]
    assert {first.pk, second.pk} == set(Payment.objects.values_list('pk', flat=True))


def test_a_filter_on_a_field_the_person_reads_still_narrows_the_list(make_user: MakeUser) -> None:
    owner = make_user()
    Loan.objects.create(applicant=owner, amount=1, status='pending')
    Loan.objects.create(applicant=owner, amount=1, status='approved')
    clerk = staff(make_user(('lending.loan_view', 'all')))

    page = admin_of(clerk).get('/admin/lending/loan/?status=pending')

    assert page.status_code == 200
    assert [loan.status for loan in page.context['cl'].result_list] == ['pending']


def test_a_date_list_is_not_offered_on_a_field_the_person_may_not_read(
    make_user: MakeUser,
) -> None:
    AccessService(actor=None).protect_field(Statement, 'issued_on')
    reader = staff(make_user('lending.view_statement'))
    allowed = staff(make_user('lending.view_statement', 'lending.view_statement_issued_on'))
    statements = protected_admin(type('Statements', (admin.ModelAdmin,), {}))
    statements.date_hierarchy = 'issued_on'
    model_admin = statements(Statement, admin.site)

    def hierarchy(person: Person) -> Any:
        request = RequestFactory().get('/admin/lending/statement/')
        request.user = person
        return model_admin.get_changelist_instance(request).date_hierarchy

    assert hierarchy(reader) is None
    assert hierarchy(allowed) == 'issued_on'


def test_a_formset_is_scoped_once_however_often_it_is_asked(make_user: MakeUser) -> None:
    formset = modelformset_factory(Loan, fields=('region',))
    scoped = formset_for(formset, make_user())

    assert formset_for(scoped, make_user()) is scoped


def test_an_action_naming_a_permission_of_the_projects_own_is_the_projects_to_scope() -> None:
    def publish(modeladmin: Any, request: Any, queryset: Any) -> None:
        """Decided by the admin's has_publish_permission: the library cannot scope it."""

    publish.allowed_permissions = ('publish',)  # type: ignore[attr-defined]

    assert _reaching(publish) is publish


# ---------------------------------------------------------------------- DRF


def test_a_superuser_chooses_any_related_row(make_user: MakeUser) -> None:
    loan = Loan.objects.create(applicant=make_user(), amount=100)
    serializer = PaymentSerializer(
        data={'loan': loan.pk, 'amount': 5}, context={'user': make_user(superuser=True)}
    )

    assert serializer.is_valid(), serializer.errors


def test_a_row_keeps_the_related_row_it_holds_though_the_person_may_not_view_it(
    make_user: MakeUser,
) -> None:
    hidden, other = (Loan.objects.create(applicant=make_user(), amount=1) for _ in range(2))
    payment = Payment.objects.create(loan=hidden, amount=5)
    clerk = make_user(('lending.view_payment', 'all'), ('lending.change_payment', 'all'))

    kept = PaymentSerializer(
        payment, data={'loan': hidden.pk, 'amount': 7}, context={'user': clerk}
    )
    moved = PaymentSerializer(
        payment, data={'loan': other.pk, 'amount': 7}, context={'user': clerk}
    )

    assert kept.is_valid(), kept.errors
    kept.save()
    assert not moved.is_valid()
    assert Payment.objects.get().amount == 7


def test_a_serializer_nested_in_a_protected_one_hides_the_field_too(make_user: MakeUser) -> None:
    class LoanBrief(serializers.ModelSerializer):  # type: ignore[type-arg]
        class Meta:
            model = Loan
            fields = ('id', 'amount', 'credit_score')

    class PaymentWithLoan(serializers.ModelSerializer):  # type: ignore[type-arg]
        loan = LoanBrief(read_only=True)

        class Meta:
            model = Payment
            fields = ('id', 'amount', 'loan')

    payment = Payment.objects.create(
        loan=Loan.objects.create(applicant=make_user(), amount=1, credit_score=700), amount=5
    )
    reader = make_user(('lending.view_payment', 'all'), ('lending.loan_view', 'all'))

    shown = protected_serializer(PaymentWithLoan)(payment, context={'user': reader}).data

    assert set(shown['loan']) == {'id', 'amount'}


# ---------------------------------------------------------------------- rows and policies


def test_a_policy_asks_a_queryset_that_answers_for_itself_about_one_row(
    make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    def northern(self: Any, user: Any, action: str = 'view') -> Any:
        return visible(self, user, action).filter(region='north')

    monkeypatch.setattr(LoanQuerySet, 'visible_to', northern, raising=False)
    reader = make_user(('lending.loan_view', 'all'))
    north = Loan.objects.create(applicant=reader, amount=1, region='north')
    south = Loan.objects.create(applicant=reader, amount=1, region='south')
    policy = registry.policy_for(Loan)

    assert policy.within_scope(reader, 'view', north)
    assert not policy.within_scope(reader, 'view', south)


def test_a_proxy_is_not_said_to_take_its_models_field_permissions() -> None:
    proxy = type(
        'ArchivedLoan',
        (Loan,),
        {
            '__module__': Loan.__module__,
            'Meta': type('Meta', (), {'proxy': True, 'app_label': 'lending'}),
        },
    )

    try:
        assert field_errors([proxy]) == []
    finally:
        del apps.all_models['lending']['archivedloan']
        apps.clear_cache()


def test_without_roles_nobody_starts_with_a_ceiling_or_reads_one_from_a_field() -> None:
    no_roles = Limits()

    assert no_roles.within_ceiling(Permission.objects.none()) == Q()
    assert no_roles.person_fields() == frozenset()


# ---------------------------------------------------------------------- roles and names


def test_a_second_limited_role_permitting_more_needs_role_ceiling_edit(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    narrow = Role.objects.create(code='clerk', name='Clerk', limited=True)
    wider = Role.objects.create(code='officer', name='Officer', limited=True)
    within = Role.objects.create(code='reader', name='Reader', limited=True)
    RoleCeiling.objects.create(role=narrow, permission=permission('lending.loan_view'))
    RoleCeiling.objects.create(role=within, permission=permission('lending.loan_view'))
    RoleCeiling.objects.create(role=wider, permission=permission('lending.loan_view'))
    RoleCeiling.objects.create(role=wider, permission=permission('lending.loan_approve'))
    clerk = make_user()
    RoleService(actor=None).assign(clerk, narrow)
    manager = make_user('clearance.permission_view', 'clearance.permission_edit')

    with pytest.raises(AccessRefused):
        RoleService(actor=manager).assign(Person.objects.get(pk=clerk.pk), wider)

    RoleService(actor=manager).assign(Person.objects.get(pk=clerk.pk), within)


def test_a_name_longer_than_its_column_is_refused(make_bundle: MakeBundle) -> None:
    with pytest.raises(ValidationError, match='longer than the 255 characters'):
        TranslationService(actor=None).name(make_bundle({}), 'fa', 'x' * 256)


def test_a_row_saved_outside_the_scope_by_a_view_of_no_model_is_not_asked_about() -> None:
    """A view that saved nothing - a form of no model - has no row to ask about."""
    from clearance.views import ScopedQuerySetMixin

    view = ScopedQuerySetMixin()
    view.request = RequestFactory().get('/')  # type: ignore[assignment]

    view.require_written_within_scope(None, creating=True)


# ---------------------------------------------------------------------- what review 9 added


def test_the_admin_sites_bulk_delete_of_rows_that_are_no_accounts_deletes_them(
    make_user: MakeUser,
) -> None:
    clerk = staff(make_user(('lending.loan_view', 'all'), ('lending.loan_delete', 'all')))
    loans = [Loan.objects.create(applicant=make_user(), amount=1) for _ in range(2)]

    admin_of(clerk).post(
        '/admin/lending/loan/',
        {
            'action': 'delete_selected',
            '_selected_action': [loan.pk for loan in loans],
            'post': 'yes',
        },
    )

    assert not Loan.objects.exists()


def test_a_view_of_no_serializer_is_guarded_by_the_names_sent(make_user: MakeUser) -> None:
    from rest_framework.response import Response
    from rest_framework.test import APIRequestFactory, force_authenticate
    from rest_framework.views import APIView

    from clearance.drf.permissions import PolicyPermission
    from tests.project.lending.policies import loan_access

    class Decide(APIView):
        permission_classes = (PolicyPermission,)
        policy = loan_access.policy
        policy_action = 'create'

        def post(self, request: Any) -> Any:
            return Response({})

    request = APIRequestFactory().post('/', {'credit_score': 900}, format='json')
    force_authenticate(request, make_user(('lending.loan_create', 'all')))

    response = Decide.as_view()(request)

    assert response.status_code == 400
    assert 'credit_score' in response.data


def test_a_serializer_used_outside_a_view_refuses_a_value_under_another_name(
    make_user: MakeUser,
) -> None:
    class Decided(serializers.ModelSerializer):  # type: ignore[type-arg]
        decision = serializers.CharField(source='status')

        class Meta:
            model = Loan
            fields = ('id', 'decision')

    editor = make_user(('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))
    loan = Loan.objects.create(applicant=editor, amount=1)
    serializer = protected_serializer(Decided)(
        loan, data={'decision': 'approved'}, context={'user': editor}
    )

    assert not serializer.is_valid()
    assert 'decision' in serializer.errors


def test_a_view_filtered_by_django_filter_with_no_filterset_lists_as_before(
    make_user: MakeUser,
) -> None:
    from django_filters.rest_framework import DjangoFilterBackend
    from rest_framework.test import APIRequestFactory, force_authenticate

    from tests.project.lending.api import LoanViewSet

    class Loans(LoanViewSet):
        filter_backends = (DjangoFilterBackend,)

    reader = make_user(('lending.loan_view', 'all'))
    Loan.objects.create(applicant=reader, amount=1)
    request = APIRequestFactory().get('/?anything=1')
    force_authenticate(request, reader)

    assert len(Loans.as_view({'get': 'list'})(request).data) == 1
