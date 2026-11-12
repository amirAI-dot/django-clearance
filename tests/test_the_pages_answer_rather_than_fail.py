"""
What the library does as it says, and its pages answer rather than fail.

If these fail, the page of a user cannot be opened in the admin site at all,
a page answers a wrong address with a server error, a list scoped by a view
is not the list the queryset itself gives, and a page reads the database once
for every bundle there is.

Each of these was a finding of the 0.1.0 review.
"""

from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import translation

from clearance.models import ScopeRule
from clearance.querysets import SignedInReadQuerySet, visible
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeBundle, MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan
from tests.project.lending.querysets import LoanQuerySet

pytestmark = pytest.mark.django_db

MANAGE = ('clearance.permission_view', 'clearance.permission_edit')


def admin_of(person: Person, **options: Any) -> Client:
    Person.objects.filter(pk=person.pk).update(is_staff=True)
    client = Client(**options)
    client.force_login(Person.objects.get(pk=person.pk))
    return client


# ---------------------------------------------------------------------- the admin site


@pytest.mark.parametrize('page', ['add/', '{pk}/change/'])
def test_the_page_of_a_user_opens_in_the_admin_site(make_user: MakeUser, page: str) -> None:
    """``UserAdmin.get_form`` takes no ``change``: the mixin hands it one, and the page is a 500."""
    owner = make_user(superuser=True)
    client = admin_of(owner, raise_request_exception=False)

    assert client.get(f'/admin/accounts/person/{page.format(pk=owner.pk)}').status_code == 200


def test_a_bundle_that_is_not_a_number_is_not_a_server_error(make_user: MakeUser) -> None:
    manager, person = make_user(*MANAGE), make_user()
    client = admin_of(manager, raise_request_exception=False)

    response = client.post(f'/admin/access/people/{person.pk}/', {'do': 'give', 'bundle': 'abc'})

    assert response.status_code in (302, 400, 404)


def test_a_refusal_is_said_in_the_readers_language(make_user: MakeUser) -> None:
    """The README: "The pages, messages and permissions come in English and Persian"."""
    manager = make_user(*MANAGE)
    bundle = Group.objects.create(name='Officers')
    client = admin_of(manager)

    with translation.override('fa'):
        page = client.post(
            f'/admin/access/people/{manager.pk}/', {'do': 'give', 'bundle': bundle.pk}, follow=True
        )

    said = [str(message) for message in page.context['messages']]
    assert said != ['Nobody changes their own access.']
    assert len(said) == 1
    assert not said[0].isascii()


def test_every_refusal_has_its_words_in_persian(make_user: MakeUser) -> None:
    """A refusal, and what is wrong with what was asked: said in Persian, each of them."""
    manager, other = make_user(*MANAGE), make_user()
    access = AccessService(actor=manager)
    refusals: list[str] = []

    def said(change: Any) -> None:
        with pytest.raises((AccessRefused, ValidationError)) as refusal:
            change()
        error = refusal.value
        refusals.extend(error.messages if isinstance(error, ValidationError) else [str(error)])

    with translation.override('fa'):
        said(lambda: access.grant(manager, 'lending.loan_view', 'all'))
        said(lambda: access.grant(other, 'lending.loan_view', 'all'))
        said(lambda: access.grant(other, 'lending.no_such', None))
        said(lambda: access.create_bundle('Readers', {}))
        said(lambda: AccessService(actor=None).create_bundle('x' * 200, {}))
        said(lambda: AccessService(actor=None).protect_field(Loan, 'id'))
        said(
            lambda: AccessService(actor=None).create_scope_rule(
                Loan, 'all', 'Every loan', [{'field': 'applicant__password', 'operator': 'is'}]
            )
        )
        said(
            lambda: AccessService(actor=None).create_status_action(
                Loan, 'view', 'View', 'amount', ['paid']
            )
        )

    assert len(refusals) >= 10
    assert [message for message in refusals if message.isascii()] == []


@pytest.mark.parametrize(
    ('page', 'sent'),
    [
        ('/admin/access/bundles/add/', {'name': 'x' * 200}),
        ('/admin/access/roles/add/', {'code': 'r' * 100, 'name': 'A role'}),
    ],
)
def test_a_name_too_long_is_refused_on_the_page(
    make_user: MakeUser, page: str, sent: dict[str, str]
) -> None:
    """SQLite keeps it whole; PostgreSQL raises ``DataError``, and the page is a 500."""
    manager = make_user(*MANAGE, 'clearance.permission_create')
    client = admin_of(manager, raise_request_exception=False)

    assert client.post(page, sent).status_code == 200  # the page again, saying what is wrong


def test_a_rule_comparing_with_nothing_is_refused_when_it_is_saved(db: None) -> None:
    """Kept in words, ``None`` was read back as ``''``: the rule then reached nothing, unsaid."""
    with pytest.raises(ValidationError, match='is_empty'):
        AccessService(actor=None).create_scope_rule(
            Loan,
            'unassigned',
            'With no officer',
            [{'field': 'officer', 'operator': 'is', 'value': {'constant': None}}],
        )

    assert not ScopeRule.objects.exists()


def test_a_name_too_long_is_refused_in_code_as_on_the_page(db: None) -> None:
    with pytest.raises(ValidationError, match='longer than the 150'):
        AccessService(actor=None).create_bundle('x' * 200, {})


# ---------------------------------------------------------------------- rows


def test_a_view_scopes_a_signed_in_read_queryset_as_the_queryset_does(
    make_user: MakeUser,
) -> None:
    """``visible()`` - what every view and the admin site call - never asks ``visible_to``."""
    Loan.objects.create(applicant=make_user(), amount=1)
    anybody = make_user()
    reference = SignedInReadQuerySet(model=Loan)

    assert reference.visible_to(anybody).count() == 1
    assert visible(reference, anybody).count() == 1


def test_a_scope_answering_with_a_queryset_keeps_the_rows_it_was_asked_about(
    make_user: MakeUser,
) -> None:
    """Alone, such a scope replaces the queryset: whatever the view had filtered by is gone."""

    class Loans(LoanQuerySet):
        scopes = {'counted': 'The loans that count'}  # noqa: RUF012

        def scope_counted(self, user: Any) -> Any:
            return Loan.objects.filter(amount__gte=0)

    owner = make_user()
    Loan.objects.create(applicant=owner, amount=5, region='north')
    Loan.objects.create(applicant=owner, amount=5, region='south')
    reader = make_user(('lending.loan_view', 'counted'))

    reached = visible(Loans(model=Loan).filter(region='north'), reader)

    assert {loan.region for loan in reached} == {'north'}


# ---------------------------------------------------------------------- queries


def queries(run: Any) -> int:
    with CaptureQueriesContext(connection) as captured:
        run()
    return len(captured)


@pytest.mark.parametrize('page', ['/admin/access/', '/admin/access/actions/'])
def test_a_page_reads_the_database_no_more_for_more_bundles(
    make_user: MakeUser, make_bundle: MakeBundle, page: str
) -> None:
    client = admin_of(make_user(superuser=True))
    make_bundle({'lending.loan_view': 'own'})
    few = queries(lambda: client.get(page))

    for _ in range(10):
        make_bundle({'lending.loan_view': 'own'})

    assert queries(lambda: client.get(page)) == few


def test_saving_a_bundle_reads_the_database_no_more_for_more_permissions(db: None) -> None:
    names = [
        'lending.loan_view',
        'lending.loan_edit',
        'lending.view_payment',
        'lending.add_payment',
    ]
    access = AccessService(actor=None)

    two = queries(lambda: access.create_bundle('Two', dict.fromkeys(names[:2], 'all')))
    four = queries(lambda: access.create_bundle('Four', dict.fromkeys(names, 'all')))

    assert four == two
