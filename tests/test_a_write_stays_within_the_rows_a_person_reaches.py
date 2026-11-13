"""
A scope narrows what a person writes as surely as what they read.

If these fail, a scope is only a filter on lists: somebody given "their own"
creates a row for anybody else, moves a row out of the rows they reach, and -
in the admin site - edits rows they may only look at, through an inline, the
editable list, or an action Django's own permissions decide.

Each of these was a finding of the 0.1.0 review.
"""

from typing import Any

import pytest
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory
from django.views.generic import DeleteView
from rest_framework import serializers
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from clearance.models import ScopeRule
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin
from clearance.writes import require_deletable, require_within_scope
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.api import PaymentList, PaymentSerializer
from tests.project.lending.models import Loan, Payment, Statement

pytestmark = pytest.mark.django_db


def staff(person: Person, **fields: Any) -> Person:
    Person.objects.filter(pk=person.pk).update(is_staff=True, **fields)
    return Person.objects.get(pk=person.pk)


def api(person: Person) -> APIClient:
    client = APIClient()
    client.force_authenticate(person)
    return client


def admin_of(person: Person) -> Client:
    client = Client()
    client.force_login(person)
    return client


def posted(form: Any) -> dict[str, Any]:
    """What a browser would send back for ``form``, unchanged."""
    data = {}

    for name, field in form.fields.items():
        if field.disabled:
            continue
        value = form[name].value()
        if value is None or value is False:
            continue
        data[form.add_prefix(name)] = 'on' if value is True else value

    return data


def region_rule() -> None:
    """The scope ``region``: the loans of the person's own region."""
    rule = ScopeRule(
        content_type=ContentType.objects.get_for_model(Loan),
        code='region',
        name='Their region',
        match='all',
    )
    rule.conditions = [{'field': 'region', 'operator': 'is', 'value': {'person': 'region'}}]
    rule.save()


# ---------------------------------------------------------------------- the API


def test_a_row_is_not_created_outside_the_scope_create_was_given_in(make_user: MakeUser) -> None:
    somebody_else = make_user()
    their_loan = Loan.objects.create(applicant=somebody_else, amount=100)
    me = make_user(('lending.view_payment', 'own'), ('lending.add_payment', 'own'))

    response = api(me).post('/api/payments/', {'loan': their_loan.pk, 'amount': 5}, format='json')

    assert response.status_code in (400, 403, 404)
    assert not Payment.objects.filter(loan=their_loan).exists()


def test_an_edit_does_not_move_a_row_out_of_the_rows_the_person_reaches(
    make_user: MakeUser,
) -> None:
    region_rule()
    me = make_user(('lending.loan_view', 'region'), ('lending.loan_edit', 'region'))
    Person.objects.filter(pk=me.pk).update(region='north')
    me = Person.objects.get(pk=me.pk)
    loan = Loan.objects.create(applicant=make_user(), amount=100, region='north')

    response = api(me).patch(f'/api/loans/{loan.pk}/', {'region': 'south'}, format='json')

    loan.refresh_from_db()
    assert response.status_code in (400, 403)
    assert loan.region == 'north'


def test_a_row_is_created_within_the_scope_create_was_given_in(make_user: MakeUser) -> None:
    me = make_user(
        ('lending.loan_view', 'own'),
        ('lending.view_payment', 'own'),
        ('lending.add_payment', 'own'),
    )
    my_loan = Loan.objects.create(applicant=me, amount=100)

    response = api(me).post('/api/payments/', {'loan': my_loan.pk, 'amount': 5}, format='json')

    assert response.status_code == 201
    assert Payment.objects.filter(loan=my_loan).count() == 1


def test_a_grant_of_create_with_no_scope_reaches_what_the_models_default_does(
    make_user: MakeUser,
) -> None:
    """A loan names no default scope, so the grant makes no loan; a payment's is ``own``."""
    me = make_user(('lending.loan_view', 'own'), 'lending.loan_create', 'lending.add_payment')
    my_loan = Loan.objects.create(applicant=me, amount=100)
    sent = {'loan': my_loan.pk, 'amount': 5}

    assert api(me).post('/api/loans/', {'amount': 50}, format='json').status_code == 403
    assert api(me).post('/api/payments/', sent, format='json').status_code == 201
    assert Loan.objects.count() == 1


def test_a_view_of_the_projects_own_asks_with_require_within_scope(make_user: MakeUser) -> None:
    me = make_user(('lending.add_payment', 'own'))
    mine = Payment.objects.create(loan=Loan.objects.create(applicant=me, amount=1), amount=5)
    theirs = Payment.objects.create(
        loan=Loan.objects.create(applicant=make_user(), amount=1), amount=5
    )

    require_within_scope(me, 'create', mine)

    with pytest.raises(PermissionDenied):
        require_within_scope(me, 'create', theirs)


# ---------------------------------------------------------------------- the admin site


def test_a_row_is_not_added_in_the_admin_site_outside_the_scope_of_create(
    make_user: MakeUser,
) -> None:
    their_loan = Loan.objects.create(applicant=make_user(), amount=100)
    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),  # every loan is offered; a payment only for their own
            ('lending.view_payment', 'own'),
            ('lending.add_payment', 'own'),
        )
    )
    my_loan = Loan.objects.create(applicant=clerk, amount=100)
    client = admin_of(clerk)

    refused = client.post(
        '/admin/lending/payment/add/', {'loan': their_loan.pk, 'amount': 5, 'state': 'due'}
    )
    made = client.post(
        '/admin/lending/payment/add/', {'loan': my_loan.pk, 'amount': 5, 'state': 'due'}
    )

    assert (refused.status_code, made.status_code) == (403, 302)
    assert [payment.loan for payment in Payment.objects.all()] == [my_loan]


def test_an_inline_still_changes_the_rows_the_person_may_edit_and_deletes_only_those(
    make_user: MakeUser,
) -> None:
    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),
            ('lending.loan_edit', 'all'),
            ('lending.view_payment', 'all'),
            ('lending.change_payment', 'own'),
            ('lending.delete_payment', 'own'),
        )
    )
    mine = Loan.objects.create(applicant=clerk, amount=100)
    theirs = Loan.objects.create(applicant=make_user(), amount=100)
    my_payment = Payment.objects.create(loan=mine, amount=5)
    their_payment = Payment.objects.create(loan=theirs, amount=5)
    client = admin_of(clerk)

    def post(loan: Loan, **change: Any) -> None:
        page = client.get(f'/admin/lending/loan/{loan.pk}/change/')
        data = posted(page.context['adminform'].form)
        for formset in page.context['inline_admin_formsets']:
            data.update(posted(formset.formset.management_form))
            for form in formset.formset.forms:
                data.update(posted(form))
                data.setdefault(form.add_prefix('id'), form.instance.pk)
                data.setdefault(form.add_prefix('loan'), loan.pk)
        client.post(f'/admin/lending/loan/{loan.pk}/change/', {**data, **change})

    post(mine, **{'payments-0-amount': 7})
    post(theirs, **{'payments-0-DELETE': 'on'})

    my_payment.refresh_from_db()
    assert my_payment.amount == 7
    assert Payment.objects.filter(pk=their_payment.pk).exists()


def test_an_inline_changes_only_the_rows_the_person_may_edit(make_user: MakeUser) -> None:
    owner = make_user()
    loan = Loan.objects.create(applicant=owner, amount=100)
    payment = Payment.objects.create(loan=loan, amount=5)
    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),
            ('lending.loan_edit', 'all'),
            ('lending.view_payment', 'all'),
            ('lending.change_payment', 'own'),  # their own payments only - this one is not
        )
    )
    client = admin_of(clerk)
    page = client.get(f'/admin/lending/loan/{loan.pk}/change/')
    data = posted(page.context['adminform'].form)

    for formset in page.context['inline_admin_formsets']:
        data.update(posted(formset.formset.management_form))
        for form in formset.formset.forms:
            data.update(posted(form))

    data['payments-0-amount'] = 999
    client.post(f'/admin/lending/loan/{loan.pk}/change/', data)

    payment.refresh_from_db()
    assert payment.amount == 5


def test_the_editable_list_changes_only_the_rows_the_person_may_edit(make_user: MakeUser) -> None:
    loan = Loan.objects.create(applicant=make_user(), amount=100, region='north')
    clerk = staff(make_user(('lending.loan_view', 'all'), ('lending.loan_edit', 'own')))
    client = admin_of(clerk)
    page = client.get('/admin/lending/loan/')
    formset = page.context['cl'].formset
    data = posted(formset.management_form)

    for form in formset.forms:
        data.update(posted(form))

    data['form-0-region'] = 'south'
    data['_save'] = 'Save'
    client.post('/admin/lending/loan/', data)

    loan.refresh_from_db()
    assert loan.region == 'north'


def test_an_action_djangos_permissions_decide_runs_over_the_rows_of_that_permission(
    make_user: MakeUser,
) -> None:
    loan = Loan.objects.create(applicant=make_user(), amount=100, region='north')
    clerk = staff(make_user(('lending.loan_view', 'all'), ('lending.loan_edit', 'own')))

    admin_of(clerk).post(
        '/admin/lending/loan/',
        {'action': 'archive', '_selected_action': [loan.pk], 'index': 0},
    )

    loan.refresh_from_db()
    assert loan.region == 'north'  # archive needs change, which they hold for their own only


def test_a_form_in_the_admin_site_offers_only_the_related_rows_the_person_reaches(
    make_user: MakeUser,
) -> None:
    loan = Loan.objects.create(applicant=make_user(), amount=123456)
    clerk = staff(make_user('lending.add_payment', 'lending.view_payment'))  # no loan at all

    page = admin_of(clerk).get('/admin/lending/payment/add/')

    assert page.status_code == 200
    assert str(loan) not in page.content.decode()  # "Loan 1 for 123456", in a <select>


def test_a_form_in_the_admin_site_keeps_the_related_row_a_row_holds_already(
    make_user: MakeUser,
) -> None:
    """Or a payment of a loan they may not view could not be saved at all."""
    loan = Loan.objects.create(applicant=make_user(), amount=123456)
    payment = Payment.objects.create(loan=loan, amount=5)
    Loan.objects.create(applicant=make_user(), amount=654321)
    clerk = staff(make_user(('lending.view_payment', 'all'), ('lending.change_payment', 'all')))
    client = admin_of(clerk)

    page = client.get(f'/admin/lending/payment/{payment.pk}/change/')
    saved = client.post(
        f'/admin/lending/payment/{payment.pk}/change/',
        {'loan': loan.pk, 'amount': 6, 'state': 'due'},
    )

    assert str(loan) in page.content.decode()
    assert 'for 654321' not in page.content.decode()
    assert saved.status_code == 302
    assert Payment.objects.get(pk=payment.pk).amount == 6


# ---------------------------------------------------------------------- many rows at once


class BulkPayments(PaymentList):
    """A list endpoint taking a list of rows, as a project's bulk create does."""

    def get_serializer(self, *args: Any, **kwargs: Any) -> Any:
        if isinstance(kwargs.get('data'), list):
            kwargs['many'] = True
        return super().get_serializer(*args, **kwargs)


def bulk_payments(person: Person, rows: list[dict[str, Any]]) -> Any:
    request = APIRequestFactory().post('/api/payments/', rows, format='json')
    force_authenticate(request, person)
    return BulkPayments.as_view()(request)


def test_rows_sent_together_are_each_created_only_within_the_scope(make_user: MakeUser) -> None:
    """One row outside the scope refuses the list, and none of it is written."""
    me = make_user(
        ('lending.loan_view', 'all'),
        ('lending.view_payment', 'own'),
        ('lending.add_payment', 'own'),
    )
    mine = Loan.objects.create(applicant=me, amount=100)
    theirs = Loan.objects.create(applicant=make_user(), amount=100)

    refused = bulk_payments(me, [{'loan': mine.pk, 'amount': 5}, {'loan': theirs.pk, 'amount': 5}])
    taken = bulk_payments(me, [{'loan': mine.pk, 'amount': 5}, {'loan': mine.pk, 'amount': 6}])

    assert refused.status_code == 403
    assert taken.status_code == 201
    assert sorted(Payment.objects.values_list('loan_id', 'amount')) == [(mine.pk, 5), (mine.pk, 6)]


def test_a_serializer_given_many_rows_creates_each_only_within_the_scope(
    make_user: MakeUser,
) -> None:
    me = make_user(('lending.loan_view', 'all'), ('lending.add_payment', 'own'))
    mine = Loan.objects.create(applicant=me, amount=100)
    theirs = Loan.objects.create(applicant=make_user(), amount=100)
    sent = [{'loan': mine.pk, 'amount': 5}, {'loan': theirs.pk, 'amount': 5}]
    serializer = PaymentSerializer(data=sent, many=True, context={'user': me})

    assert serializer.is_valid(), serializer.errors
    with pytest.raises(PermissionDenied):
        serializer.save()

    assert not Payment.objects.exists()


class PlainBulkPayments(BulkPayments):
    """The same, with a serializer the library never touched: the view asks for each row."""

    def get_serializer_class(self) -> Any:
        class Plain(serializers.ModelSerializer):  # type: ignore[type-arg]
            class Meta:
                model = Payment
                fields = ('id', 'loan', 'amount')

        return Plain


def test_a_view_asks_for_each_row_of_a_list_whatever_its_serializer(make_user: MakeUser) -> None:
    me = make_user(
        ('lending.loan_view', 'all'),
        ('lending.view_payment', 'own'),
        ('lending.add_payment', 'own'),
    )
    mine = Loan.objects.create(applicant=me, amount=100)
    theirs = Loan.objects.create(applicant=make_user(), amount=100)
    request = APIRequestFactory().post(
        '/api/payments/',
        [{'loan': mine.pk, 'amount': 5}, {'loan': theirs.pk, 'amount': 5}],
        format='json',
    )
    force_authenticate(request, me)

    assert PlainBulkPayments.as_view()(request).status_code == 403
    assert not Payment.objects.exists()


# ---------------------------------------------------------------------- what a delete takes with it


def test_a_delete_takes_no_row_the_person_may_not_delete(make_user: MakeUser) -> None:
    """Deleting a loan deleted its payments too, for somebody allowed to delete no payment."""
    clerk = make_user(('lending.loan_view', 'all'), ('lending.loan_delete', 'all'))
    loan = Loan.objects.create(applicant=make_user(), amount=1)
    Payment.objects.create(loan=loan, amount=7)

    response = api(clerk).delete(f'/api/loans/{loan.pk}/')

    assert response.status_code == 403
    assert Loan.objects.filter(pk=loan.pk).exists()
    assert Payment.objects.count() == 1


def test_a_delete_takes_the_rows_of_every_model_the_person_may_delete(
    make_user: MakeUser,
) -> None:
    """A statement keeps Django's permissions and a plain manager: its ``delete`` is asked too."""
    grants = (
        ('lending.loan_view', 'all'),
        ('lending.loan_delete', 'all'),
        ('lending.delete_payment', 'all'),
    )
    loan = Loan.objects.create(applicant=make_user(), amount=1)
    Payment.objects.create(loan=loan, amount=7)
    Statement.objects.create(loan=loan, total=7)

    assert api(make_user(*grants)).delete(f'/api/loans/{loan.pk}/').status_code == 403
    assert Statement.objects.count() == 1

    clerk = make_user(*grants, 'lending.delete_statement')
    assert api(clerk).delete(f'/api/loans/{loan.pk}/').status_code == 204
    assert (Loan.objects.count(), Payment.objects.count(), Statement.objects.count()) == (0, 0, 0)


class LoanDelete(PolicyRequiredMixin, ScopedQuerySetMixin, DeleteView):  # type: ignore[misc, type-arg]
    queryset = Loan.objects.all()
    success_url = '/loans/'


def deleted_by_view(person: Person, loan: Loan) -> Any:
    request = RequestFactory().post('/')
    request.user = person
    return LoanDelete.as_view()(request, pk=loan.pk)


def test_a_django_delete_view_deletes_within_the_scope_and_what_goes_with_it(
    make_user: MakeUser,
) -> None:
    clerk = make_user(('lending.loan_view', 'own'), ('lending.loan_delete', 'own'))
    bare, paid = (Loan.objects.create(applicant=clerk, amount=1) for _ in range(2))
    Payment.objects.create(loan=paid, amount=7)  # theirs to see, not to delete

    assert deleted_by_view(clerk, bare).status_code == 302
    with pytest.raises(PermissionDenied):
        deleted_by_view(clerk, paid)
    assert list(Loan.objects.all()) == [paid]


def test_the_admin_site_deletes_nothing_a_cascade_takes_outside_the_scope(
    make_user: MakeUser,
) -> None:
    clerk = staff(make_user(('lending.loan_view', 'all'), ('lending.loan_delete', 'all')))
    loan = Loan.objects.create(applicant=make_user(), amount=1)
    Payment.objects.create(loan=loan, amount=7)
    request = RequestFactory().post('/')
    request.user = clerk
    loans = admin.site._registry[Loan]

    with pytest.raises(PermissionDenied):
        loans.delete_queryset(request, Loan.objects.all())
    with pytest.raises(PermissionDenied):
        loans.delete_model(request, loan)
    assert Payment.objects.count() == 1


def test_deleting_nothing_asks_nothing(make_user: MakeUser) -> None:
    require_deletable(make_user(), Loan.objects.none())


# ---------------------------------------------------------------------- a policy's own hooks


@pytest.fixture
def approved_stays(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rule no scope can say: an approved loan is neither edited nor deleted."""
    from tests.project.lending.policies import LoanPolicy

    def unless_approved(action: str) -> Any:
        def hook(self: Any, user: Any, obj: Any = None) -> bool:
            if not self.has_within_scope(user, action, obj):
                return False
            return obj is None or getattr(obj, 'status', None) != 'approved'

        return hook

    monkeypatch.setattr(LoanPolicy, 'can_edit', unless_approved('edit'), raising=False)
    monkeypatch.setattr(LoanPolicy, 'can_delete', unless_approved('delete'), raising=False)


def test_the_editable_list_asks_the_policys_own_hook_of_each_row(
    make_user: MakeUser, approved_stays: None
) -> None:
    """Before Django 6.1 asked each row itself, the list changed what the hook refuses."""
    owner = make_user()
    approved = Loan.objects.create(applicant=owner, amount=1, region='north', status='approved')
    pending = Loan.objects.create(applicant=owner, amount=1, region='north')
    clerk = staff(make_user(('lending.loan_view', 'all'), ('lending.loan_edit', 'all')))
    client = admin_of(clerk)
    page = client.get('/admin/lending/loan/')
    formset = page.context['cl'].formset
    data = posted(formset.management_form)

    for form in formset.forms:
        data.update(posted(form))
        data[form.add_prefix('id')] = form.instance.pk
        data[form.add_prefix('region')] = 'south'

    data['_save'] = 'Save'
    client.post('/admin/lending/loan/', data)

    approved.refresh_from_db()
    pending.refresh_from_db()
    assert (approved.region, pending.region) == ('north', 'south')


def test_an_inline_asks_the_policys_own_hook_of_each_row(
    make_user: MakeUser, approved_stays: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A payment, not a loan, is the inline's row: its policy's hook is asked."""
    from clearance.registry import registry

    payments = registry.policy_for(Payment)
    monkeypatch.setattr(
        type(payments),
        'can_edit',
        lambda self, user, obj=None: obj is None or obj.state != 'paid',
        raising=False,
    )
    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),
            ('lending.loan_edit', 'all'),
            ('lending.view_payment', 'all'),
            ('lending.change_payment', 'all'),
        )
    )
    loan = Loan.objects.create(applicant=clerk, amount=100)
    paid = Payment.objects.create(loan=loan, amount=5, state='paid')
    due = Payment.objects.create(loan=loan, amount=5)
    client = admin_of(clerk)
    page = client.get(f'/admin/lending/loan/{loan.pk}/change/')
    data = posted(page.context['adminform'].form)

    for formset in page.context['inline_admin_formsets']:
        data.update(posted(formset.formset.management_form))
        for form in formset.formset.forms:
            data.update(posted(form))
            data[form.add_prefix('id')] = form.instance.pk
            data[form.add_prefix('loan')] = loan.pk
            data[form.add_prefix('amount')] = 9

    client.post(f'/admin/lending/loan/{loan.pk}/change/', data)

    paid.refresh_from_db()
    due.refresh_from_db()
    assert (paid.amount, due.amount) == (5, 9)


def test_an_inline_with_no_hook_of_its_own_reads_its_rows_in_a_fixed_number_of_queries(
    make_user: MakeUser,
) -> None:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    clerk = staff(
        make_user(
            ('lending.loan_view', 'all'),
            ('lending.loan_edit', 'all'),
            ('lending.view_payment', 'all'),
            ('lending.change_payment', 'own'),
        )
    )
    loan = Loan.objects.create(applicant=clerk, amount=100)
    client = admin_of(clerk)

    def page() -> int:
        with CaptureQueriesContext(connection) as queries:
            client.get(f'/admin/lending/loan/{loan.pk}/change/')
        return len(queries)

    Payment.objects.create(loan=loan, amount=1)
    one = page()
    Payment.objects.bulk_create(Payment(loan=loan, amount=2) for _ in range(5))

    assert page() == one
