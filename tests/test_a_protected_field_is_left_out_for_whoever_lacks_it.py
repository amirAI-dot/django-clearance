"""
A protected field is read only with its view permission and written only with
its edit permission - in code, in a form, on a page and in a template.

If these fail, a loan officer's credit score is shown to every customer who
reads their own loan, a form lets somebody change a field they were only
allowed to see, or a field marked protected in the database is protected
nowhere at all.
"""

from typing import Any

import pytest
from django import forms
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.views.generic import TemplateView
from django.views.generic.edit import FormMixin
from pytest_django import DjangoAssertNumQueries

from clearance.fields import Protection, readable_fields, writable_fields
from clearance.forms import ProtectedFieldsFormMixin
from clearance.permissions import (
    DeclaredPermissions,
    build_permissions,
    declared_protected_fields,
    field_permission,
    resource_codename,
)
from clearance.services import AccessService
from clearance.views import ProtectedFieldsViewMixin
from tests.conftest import MakeBundle, MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment, Statement

SCORE_VIEW, SCORE_EDIT = 'lending.loan_view_credit_score', 'lending.loan_edit_credit_score'
EVERY_LOAN_FIELD = frozenset(
    {'id', 'applicant', 'officer', 'amount', 'approved', 'region', 'status', 'credit_score'}
)


class LoanForm(ProtectedFieldsFormMixin, forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Loan
        fields = ('amount', 'region', 'credit_score')


def fresh(person: Person) -> Person:
    """The person as the next request reads them - nothing kept from before."""
    return Person.objects.get(pk=person.pk)


# ---------------------------------------------------------------- declaring


def test_a_field_protected_in_code_has_two_permissions_of_its_own() -> None:
    declared = build_permissions('loan', 'loans', actions=('view',), protected_fields=('rate',))

    assert list(declared) == [
        ('loan_view', 'Can view loans'),
        ('loan_view_rate', 'Can view rate of loans'),
        ('loan_edit_rate', 'Can edit rate of loans'),
    ]
    assert isinstance(declared, DeclaredPermissions)
    assert (declared.codename, declared.protected_fields) == ('loan', ('rate',))


@pytest.mark.parametrize(
    ('fields', 'actions', 'message'),
    [
        (('Rate',), ('view',), 'is not a field name'),
        (('rate', 'rate'), ('view',), 'protects rate more than once'),
        (('rate',), ('view', 'view_rate'), 'both as an action and as the permission'),
    ],
)
def test_a_protected_field_that_could_not_work_is_refused_where_it_is_declared(
    fields: tuple[str, ...], actions: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ImproperlyConfigured, match=message):
        build_permissions('loan', 'loans', actions=actions, protected_fields=fields)


def test_a_fields_permissions_are_named_in_the_style_of_their_model() -> None:
    assert field_permission(Loan, 'credit_score', 'view') == SCORE_VIEW
    assert field_permission(Loan, 'credit_score', 'edit') == SCORE_EDIT
    assert field_permission(Payment, 'amount', 'view') == 'lending.view_payment_amount'
    assert field_permission(Payment, 'amount', 'edit') == 'lending.change_payment_amount'
    assert (resource_codename(Loan), resource_codename(Payment)) == ('loan', 'payment')
    assert declared_protected_fields(Loan) == ('credit_score',)
    assert declared_protected_fields(Payment) == ()

    with pytest.raises(ValueError, match="not 'delete'"):
        field_permission(Loan, 'credit_score', 'delete')


# ---------------------------------------------------------------- reading and writing


def test_without_the_view_permission_the_field_is_not_there(make_user: MakeUser) -> None:
    person = make_user('lending.loan_view')

    assert readable_fields(person, Loan) == EVERY_LOAN_FIELD - {'credit_score'}
    assert writable_fields(person, Loan) == EVERY_LOAN_FIELD - {'credit_score'}


def test_the_view_permission_reads_it_and_the_edit_permission_writes_it(
    make_user: MakeUser,
) -> None:
    reader, writer = make_user(SCORE_VIEW), make_user(SCORE_VIEW, SCORE_EDIT)

    assert 'credit_score' in readable_fields(reader, Loan)
    assert 'credit_score' not in writable_fields(reader, Loan)
    assert 'credit_score' in writable_fields(writer, Loan)


def test_a_field_that_may_not_be_read_may_not_be_written_either(make_user: MakeUser) -> None:
    person = make_user(SCORE_EDIT)

    assert 'credit_score' not in writable_fields(person, Loan), 'a form would show what it holds'


def test_a_bundle_gives_a_field_and_a_revocation_takes_it_away(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    officers = make_bundle({SCORE_VIEW: None})
    person = make_user(bundles=(officers,))

    assert 'credit_score' in readable_fields(person, Loan)

    AccessService(actor=None).revoke(person, SCORE_VIEW)
    assert 'credit_score' not in readable_fields(fresh(person), Loan)


def test_the_superuser_reads_and_writes_every_field(make_user: MakeUser) -> None:
    superuser = make_user(superuser=True)

    assert readable_fields(superuser, Loan) == writable_fields(superuser, Loan) == EVERY_LOAN_FIELD
    assert 'credit_score' not in readable_fields(make_user(superuser=True, active=False), Loan)


def test_somebody_signed_out_reads_only_what_nobody_protected(db: None) -> None:
    assert readable_fields(AnonymousUser(), Loan) == EVERY_LOAN_FIELD - {'credit_score'}


def test_a_field_marked_in_the_database_is_protected_like_one_in_code(
    make_user: MakeUser,
) -> None:
    AccessService(actor=None).protect_field(Payment, 'amount')
    person, holder = make_user(), make_user('lending.view_payment_amount')

    assert 'amount' not in readable_fields(person, Payment)
    assert 'amount' in readable_fields(holder, Payment)
    assert readable_fields(person, Statement) == {'id', 'loan', 'region', 'total', 'issued_on'}


def test_a_model_with_nothing_protected_gives_every_field(make_user: MakeUser) -> None:
    assert writable_fields(make_user(), Payment) == {'id', 'loan', 'amount', 'state'}


def test_what_is_protected_is_read_once_per_request(
    make_user: MakeUser, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    person = fresh(make_user(SCORE_VIEW))

    with django_assert_num_queries(2):  # what is protected, their grants
        readable_fields(person, Loan)
        writable_fields(person, Loan)

    with django_assert_num_queries(0):
        readable_fields(person, Loan)
        readable_fields(person, Payment)


def test_the_protection_knows_which_permissions_belong_to_a_field(db: None) -> None:
    protection = Protection.load()

    assert protection.owns(Loan, SCORE_VIEW)
    assert not protection.owns(Loan, 'lending.loan_view')
    assert protection.adding(Payment, 'amount').protects(Payment, 'amount')
    assert not protection.protects(Payment, 'amount')


# ---------------------------------------------------------------- a form


def test_a_form_leaves_out_what_may_not_be_read(make_user: MakeUser) -> None:
    form = LoanForm(user=make_user())

    assert list(form.fields) == ['amount', 'region']


def test_a_form_shows_disabled_what_may_be_read_but_not_written(make_user: MakeUser) -> None:
    form = LoanForm(user=make_user(SCORE_VIEW))

    assert form.fields['credit_score'].disabled
    assert not form.fields['amount'].disabled, 'what nobody protected is left as declared'


def test_a_value_sent_for_a_disabled_field_is_not_saved(make_user: MakeUser) -> None:
    loan = Loan.objects.create(applicant=make_user(), amount=100, credit_score=600)
    data = {'amount': 200, 'region': 'north', 'credit_score': 850}

    form = LoanForm(data, instance=loan, user=make_user(SCORE_VIEW))
    assert form.is_valid(), form.errors
    form.save()

    loan.refresh_from_db()
    assert (loan.amount, loan.credit_score) == (200, 600)


def test_a_form_that_forgot_whose_it_is_is_not_built() -> None:
    with pytest.raises(TypeError, match='user'):
        LoanForm()  # type: ignore[call-arg]


def test_a_form_with_no_model_cannot_protect_one(db: None) -> None:
    class Plain(ProtectedFieldsFormMixin, forms.Form):
        pass

    with pytest.raises(ImproperlyConfigured, match='use it on a ModelForm'):
        Plain(user=AnonymousUser())


# ---------------------------------------------------------------- a page


@pytest.fixture
def loan(make_user: MakeUser) -> Loan:
    return Loan.objects.create(applicant=make_user(), amount=100, region='north', credit_score=600)


EDITOR = (('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))


def page(client: Client, person: Person, address: str) -> str:
    client.force_login(person)
    response = client.get(address)
    assert response.status_code == 200
    return response.content.decode()


def test_a_page_leaves_the_field_out_of_its_form(
    client: Client, make_user: MakeUser, loan: Loan
) -> None:
    html = page(client, make_user(*EDITOR), f'/loans/{loan.pk}/edit/')

    assert 'name="amount"' in html
    assert 'credit_score' not in html


def test_a_page_shows_it_disabled_to_whoever_may_only_read_it(
    client: Client, make_user: MakeUser, loan: Loan
) -> None:
    html = page(client, make_user(*EDITOR, SCORE_VIEW), f'/loans/{loan.pk}/edit/')

    assert 'name="credit_score"' in html
    assert 'disabled' in html


def test_a_page_saves_the_field_only_for_whoever_may_write_it(
    client: Client, make_user: MakeUser, loan: Loan
) -> None:
    sent = {'amount': 150, 'region': 'north', 'credit_score': 900, 'status': 'pending'}
    client.force_login(make_user(*EDITOR))
    assert client.post(f'/loans/{loan.pk}/edit/', sent).status_code == 302
    loan.refresh_from_db()
    assert (loan.amount, loan.credit_score) == (150, 600), 'the score was not theirs to send'

    client.force_login(make_user(*EDITOR, SCORE_VIEW, SCORE_EDIT))
    assert client.post(f'/loans/{loan.pk}/edit/', sent).status_code == 302
    loan.refresh_from_db()
    assert loan.credit_score == 900


def test_a_template_is_told_what_may_be_read_and_reads_the_permissions_too(
    client: Client, make_user: MakeUser, loan: Loan
) -> None:
    reader = ('lending.loan_view', 'all')

    assert page(client, make_user(reader), f'/loans/{loan.pk}/') == f'loan:{loan.pk}'
    assert page(client, make_user(reader, SCORE_VIEW), f'/loans/{loan.pk}/') == (
        f'loan:{loan.pk} score:600'
    )
    assert page(client, make_user(reader, SCORE_VIEW, SCORE_EDIT), f'/loans/{loan.pk}/') == (
        f'loan:{loan.pk} score:600 may-edit-score'
    )


def test_a_form_already_protecting_its_fields_is_used_as_it_is() -> None:
    class Edit(ProtectedFieldsViewMixin, FormMixin):  # type: ignore[type-arg]
        form_class = LoanForm

    assert Edit().get_form_class() is LoanForm


def test_a_page_with_no_model_tells_its_template_nothing(rf: Any, db: None) -> None:
    class About(ProtectedFieldsViewMixin, TemplateView):
        pass

    view = About()
    view.setup(rf.get('/'))
    view.request.user = AnonymousUser()

    assert 'readable_fields' not in view.get_context_data()
