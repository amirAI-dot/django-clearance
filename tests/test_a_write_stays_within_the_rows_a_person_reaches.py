"""
A scope narrows what a person writes as surely as what they read.

If these fail, a scope is only a filter on lists: somebody given "their own"
creates a row for anybody else, moves a row out of the rows they reach, and -
in the admin site - edits rows they may only look at, through an inline, the
editable list, or an action Django's own permissions decide.

Each of these is a finding of the 0.1.0 review. One not yet fixed is marked
``xfail`` - strictly, so the mark is taken off by whoever fixes it.
"""

from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from rest_framework.test import APIClient

from clearance.models import ScopeRule
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment

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


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_row_is_not_created_outside_the_scope_create_was_given_in(make_user: MakeUser) -> None:
    somebody_else = make_user()
    their_loan = Loan.objects.create(applicant=somebody_else, amount=100)
    me = make_user(('lending.view_payment', 'own'), ('lending.add_payment', 'own'))

    response = api(me).post('/api/payments/', {'loan': their_loan.pk, 'amount': 5}, format='json')

    assert response.status_code in (400, 403, 404)
    assert not Payment.objects.filter(loan=their_loan).exists()


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
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


# ---------------------------------------------------------------------- the admin site


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
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


@pytest.mark.xfail(
    reason='A finding of the 0.1.0 review, fixed in a later stage - and by Django itself from 6.1.',
    strict=False,
)
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


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
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


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_form_in_the_admin_site_offers_only_the_related_rows_the_person_reaches(
    make_user: MakeUser,
) -> None:
    loan = Loan.objects.create(applicant=make_user(), amount=123456)
    clerk = staff(make_user('lending.add_payment', 'lending.view_payment'))  # no loan at all

    page = admin_of(clerk).get('/admin/lending/payment/add/')

    assert page.status_code == 200
    assert str(loan) not in page.content.decode()  # "Loan 1 for 123456", in a <select>
