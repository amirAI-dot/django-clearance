"""
Django's admin site asks the library on every page, for every ModelAdmin a
project registers - with no mixin written.

If these fail, the admin site is the way round every rule: a clerk reads
every loan there, sorts and searches by a credit score kept for officers,
edits it in the list, approves a loan by choosing "approved", runs an action
nobody gave them, or makes themselves a superuser.
"""

import gc
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.test import Client, RequestFactory

from clearance.admin.checks import admin_site_errors, check_admin_sites
from clearance.admin.discovery import AdminActionFinder
from clearance.admin.options import (
    BoundToUserFormMixin,
    ClearanceModelAdminMixin,
    _without,
    form_for,
    protected_admin,
)
from clearance.fields import path_readable
from clearance.models import ProtectedField
from tests.conftest import MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.admin import LoanAdmin
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

SCORE = ('lending.loan_view_credit_score', 'lending.loan_edit_credit_score')
READER = ('lending.loan_view', 'all')
EDITOR = (READER, ('lending.loan_edit', 'all'))


@pytest.fixture
def make_staff(make_user: MakeUser) -> Any:
    def make(*permissions: Any, superuser: bool = False) -> Person:
        person = make_user(*permissions, superuser=superuser)
        person.is_staff = True
        person.save()
        return Person.objects.get(pk=person.pk)

    return make


@pytest.fixture
def loan(make_user: MakeUser) -> Loan:
    return Loan.objects.create(applicant=make_user(), amount=100, credit_score=600)


def loan_admin() -> Any:
    return admin.site._registry[Loan]


def request_by(person: Person) -> Any:
    request = RequestFactory().get('/')
    request.user = person
    return request


def page(client: Client, person: Person, address: str) -> Any:
    client.force_login(person)
    return client.get(address)


# ---------------------------------------------------------------- the site


def test_every_registered_admin_asks_the_library_with_no_mixin_written() -> None:
    assert isinstance(loan_admin(), ClearanceModelAdminMixin)
    assert isinstance(loan_admin(), LoanAdmin)
    assert type(loan_admin()).__name__ == 'LoanAdmin'
    assert protected_admin(LoanAdmin) is protected_admin(LoanAdmin)


def test_djangos_own_group_page_is_gone() -> None:
    assert not admin.site.is_registered(Group)


def test_an_admin_site_that_is_not_the_librarys_is_refused_at_start_up() -> None:
    other = admin.AdminSite(name='other')

    assert [error.id for error in admin_site_errors([other])] == ['clearance.E016']
    del other
    gc.collect()
    assert check_admin_sites() == [], "the project itself uses the library's site"


# ---------------------------------------------------------------- who, and which rows


def test_a_page_needs_the_models_permission(client: Client, make_staff: Any, loan: Loan) -> None:
    assert page(client, make_staff(), '/admin/lending/loan/').status_code == 403
    assert page(client, make_staff(READER), '/admin/lending/loan/').status_code == 200


def test_the_list_shows_only_the_rows_reached(
    client: Client, make_staff: Any, make_user: MakeUser, loan: Loan
) -> None:
    clerk = make_staff(('lending.loan_view', 'own'))
    own = Loan.objects.create(applicant=clerk, amount=5)

    html = page(client, clerk, '/admin/lending/loan/').content.decode()

    assert f'/admin/lending/loan/{own.pk}/change/' in html
    assert f'/admin/lending/loan/{loan.pk}/change/' not in html
    assert page(client, clerk, f'/admin/lending/loan/{loan.pk}/change/').status_code == 302


def test_editing_needs_the_edit_permission_on_that_row(make_staff: Any, loan: Loan) -> None:
    reader, editor = make_staff(READER), make_staff(*EDITOR)

    assert not loan_admin().has_change_permission(request_by(reader), loan)
    assert loan_admin().has_change_permission(request_by(editor), loan)
    assert loan_admin().has_view_permission(request_by(editor), loan)
    assert not loan_admin().has_add_permission(request_by(editor))
    assert not loan_admin().has_delete_permission(request_by(editor), loan)


# ---------------------------------------------------------------- which fields


def test_a_field_that_may_not_be_read_is_nowhere_in_the_list(make_staff: Any) -> None:
    request = request_by(make_staff(READER))

    assert 'credit_score' not in loan_admin().get_list_display(request)
    assert loan_admin().get_list_filter(request) == ['status']
    assert loan_admin().get_search_fields(request) == ['region', 'applicant__username']
    assert loan_admin().get_ordering(request) == ['id']
    assert 'credit_score' not in loan_admin().get_sortable_by(request)


def test_a_field_that_may_be_read_is_in_the_list_again(make_staff: Any) -> None:
    request = request_by(make_staff(READER, SCORE[0]))

    assert 'credit_score' in loan_admin().get_list_display(request)
    assert loan_admin().get_ordering(request) == ['-credit_score', 'id']


def test_a_column_is_edited_in_the_list_only_by_whoever_may_write_it(
    make_staff: Any,
) -> None:
    assert loan_admin().editable(request_by(make_staff(*EDITOR, SCORE[0]))) == ('region',)
    assert loan_admin().editable(request_by(make_staff(*EDITOR, *SCORE))) == (
        'region',
        'credit_score',
    )
    formset = loan_admin().get_changelist_formset(request_by(make_staff(*EDITOR)))
    assert 'credit_score' not in formset.form.base_fields


def test_the_change_page_leaves_out_or_locks_the_field(
    client: Client, make_staff: Any, loan: Loan
) -> None:
    address = f'/admin/lending/loan/{loan.pk}/change/'

    hidden = page(client, make_staff(*EDITOR), address).content.decode()
    assert 'credit_score' not in hidden

    locked = page(client, make_staff(*EDITOR, SCORE[0]), address)
    assert 'name="credit_score"' not in locked.content.decode()
    assert locked.context['adminform'].readonly_fields == ['credit_score']

    open_ = page(client, make_staff(*EDITOR, *SCORE), address).content.decode()
    assert 'name="credit_score"' in open_


def test_a_line_of_fields_loses_only_the_field_it_may_not_show() -> None:
    fields = ['applicant', 'credit_score', ('amount', 'credit_score'), ('credit_score',)]

    assert _without(fields, frozenset({'credit_score'})) == ['applicant', ('amount',)]


def test_the_change_page_offers_only_the_status_values_the_person_may_set(
    client: Client, make_staff: Any, loan: Loan
) -> None:
    editor = make_staff(*EDITOR)
    address = f'/admin/lending/loan/{loan.pk}/change/'

    assert 'value="approved"' not in page(client, editor, address).content.decode()

    sent = {
        'applicant': loan.applicant_id,
        'amount': 100,
        'region': '',
        'status': 'approved',
        'payments-TOTAL_FORMS': 0,
        'payments-INITIAL_FORMS': 0,
    }
    refused = client.post(address, sent)
    assert refused.status_code == 200, 'shown again, with the error'
    loan.refresh_from_db()
    assert loan.status == 'pending'


def test_an_inline_hides_its_own_models_protected_fields(
    client: Client, make_staff: Any, loan: Loan
) -> None:
    Payment.objects.create(loan=loan, amount=7)
    clerk = make_staff(*EDITOR, ('lending.view_payment', 'all'))
    address = f'/admin/lending/loan/{loan.pk}/change/'

    shown = page(client, clerk, address).content.decode()
    assert 'column-amount' in shown
    assert 'column-state' in shown

    ProtectedField.objects.create(
        content_type=ContentType.objects.get_for_model(Payment), field='amount'
    )
    hidden = page(client, make_staff(*EDITOR, ('lending.view_payment', 'all')), address)
    assert 'column-amount' not in hidden.content.decode()
    assert 'column-state' in hidden.content.decode()


def test_an_inline_asks_its_own_models_policy(make_staff: Any, loan: Loan) -> None:
    request = request_by(make_staff(*EDITOR, 'lending.view_payment'))
    (inline,) = loan_admin().get_inline_instances(request, loan)

    assert inline.has_view_permission(request, loan)
    assert not inline.has_add_permission(request, loan)
    assert not inline.has_change_permission(request, loan)
    assert not inline.has_delete_permission(request, loan)


def test_a_form_already_protected_is_used_as_it_is(make_staff: Any) -> None:
    form = loan_admin().get_form(request_by(make_staff(*EDITOR)))

    assert issubclass(form, BoundToUserFormMixin)
    assert form_for(form, make_staff()) is form


# ---------------------------------------------------------------- the user model


def test_a_persons_own_access_is_read_only_on_the_user_page(make_staff: Any) -> None:
    users = admin.site._registry[Person]
    clerk = make_staff('accounts.change_person')

    locked = users.get_readonly_fields(request_by(clerk))
    assert {'groups', 'user_permissions', 'is_superuser'} <= set(locked)

    by_superuser = users.get_readonly_fields(request_by(make_staff(superuser=True)))
    assert 'is_superuser' not in by_superuser
    assert {'groups', 'user_permissions'} <= set(by_superuser)


# ---------------------------------------------------------------- actions


def test_an_admin_action_is_offered_only_to_whoever_holds_it(make_staff: Any) -> None:
    editor = make_staff(*EDITOR)
    holder = make_staff(*EDITOR, ('lending.loan_mark_reviewed', 'all'))
    remover = make_staff(READER, ('lending.loan_delete', 'all'))

    assert set(loan_admin().get_actions(request_by(editor))) == {'archive'}
    assert set(loan_admin().get_actions(request_by(holder))) == {'archive', 'mark_reviewed'}
    assert set(loan_admin().get_actions(request_by(remover))) == {'delete_selected'}


def test_an_admin_action_runs_only_over_the_rows_its_scope_reaches(
    client: Client, make_staff: Any, make_user: MakeUser, loan: Loan
) -> None:
    clerk = make_staff(READER, ('lending.loan_mark_reviewed', 'own'))
    own = Loan.objects.create(applicant=clerk, amount=5)
    client.force_login(clerk)

    client.post(
        '/admin/lending/loan/',
        {'action': 'mark_reviewed', '_selected_action': [loan.pk, own.pk], 'index': 0},
    )

    assert Loan.objects.get(pk=own.pk).region == 'reviewed'
    assert Loan.objects.get(pk=loan.pk).region == '', 'selected, but not in their scope'


def test_the_actions_found_are_those_nobody_wrote_a_permission_for() -> None:
    found = {action.permission for action in AdminActionFinder().find()}

    assert 'lending.loan_mark_reviewed' in found
    assert 'lending.loan_archive' not in found, "Django's change permission decides it"
    assert not any(name.endswith('delete_selected') for name in found)


# ---------------------------------------------------------------- reading a path


def test_a_lookup_through_a_relation_reads_the_field_at_its_end(make_user: MakeUser) -> None:
    ProtectedField.objects.create(
        content_type=ContentType.objects.get_for_model(Person), field='region'
    )
    person = make_user()

    assert not path_readable(person, Loan, 'applicant__region')
    assert not path_readable(person, Loan, '-credit_score')
    assert path_readable(person, Loan, 'region__icontains')
    assert path_readable(person, Loan, 'applicant__username')
    assert path_readable(person, Loan, 'payments__amount')


# ---------------------------------------------------------------- the edges


def test_an_admin_given_the_hooks_twice_has_them_once() -> None:
    once = protected_admin(LoanAdmin)

    assert protected_admin(once) is once


def test_starting_again_with_the_group_page_already_gone_changes_nothing() -> None:
    from django.apps import apps

    apps.get_app_config('admin').ready()

    assert not admin.site.is_registered(Group)


def test_a_lookup_past_the_last_relation_reads_nothing_more(make_user: MakeUser) -> None:
    assert path_readable(make_user(), Loan, 'applicant__isnull')


def test_without_the_admin_site_neither_its_actions_nor_its_checks_are_looked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.apps import apps
    from django.core import checks

    from clearance.discovery import default_finders

    registered: list[Any] = []
    monkeypatch.setattr(apps, 'is_installed', lambda name: name != 'django.contrib.admin')
    monkeypatch.setattr(checks, 'register', lambda check, *tags: registered.append(check))

    apps.get_app_config('clearance').ready()

    assert check_admin_sites not in registered
    assert 'AdminActionFinder' not in [type(finder).__name__ for finder in default_finders()]
