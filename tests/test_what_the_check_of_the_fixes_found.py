"""
What a check of the review's fixes found - four ways round them, each held.

If these fail, the editable list of accounts changes a manager's e-mail
address for somebody holding less, a person moves themselves to another
region on their own page, an account "of their branch" is taken over by
somebody of another branch, and deleting a user takes rows nobody gave them.
"""

from typing import Any

import pytest
from django import forms
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from clearance.admin.options import protected_admin
from clearance.forms import ProtectedFieldsFormMixin
from clearance.models import ScopeRule
from clearance.registry import registry
from clearance.safety import outranks, own_fields
from clearance.writes import refused_writes, require_deletable
from tests.conftest import MakeBundle, MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan

pytestmark = pytest.mark.django_db

PEOPLE = (('accounts.view_person', 'all'), ('accounts.change_person', 'all'))
LOANS = (('lending.loan_view', 'region'), ('lending.loan_edit', 'region'))


def fresh(person: Person, **fields: Any) -> Person:
    Person.objects.filter(pk=person.pk).update(**fields)
    return Person.objects.get(pk=person.pk)


def region_rule(code: str = 'region', person: bool = True) -> None:
    """``region``: the loans of the person's own region - or, not of the person's, of the north."""
    value: dict[str, Any] = {'person': 'region'} if person else {'constant': 'north'}
    rule = ScopeRule(
        content_type=ContentType.objects.get_for_model(Loan), code=code, name=code, match='all'
    )
    rule.conditions = [{'field': 'region', 'operator': 'is', 'value': value}]
    rule.save()


class People(admin.ModelAdmin):  # type: ignore[type-arg]
    """An admin of the project's own, as Django documents one - with a list to edit."""

    list_display = ('username', 'email', 'region')
    list_editable = ('email', 'region')


def saved_in_the_list(actor: Person, **change: dict[str, str]) -> None:
    """The editable list of accounts, sent back by ``actor`` with ``change`` - by person's key."""
    people = list(Person.objects.order_by('pk'))
    data: dict[str, Any] = {
        'form-TOTAL_FORMS': len(people),
        'form-INITIAL_FORMS': len(people),
        'form-MIN_NUM_FORMS': 0,
        'form-MAX_NUM_FORMS': 1000,
        '_save': 'Save',
    }

    for number, person in enumerate(people):
        sent = {'email': person.email, 'region': person.region, **change.get(str(person.pk), {})}
        data.update({f'form-{number}-id': person.pk})
        data.update({f'form-{number}-{name}': value for name, value in sent.items()})

    request = RequestFactory().post('/admin/accounts/person/', data)
    request.user = actor
    request._dont_enforce_csrf_checks = True  # type: ignore[attr-defined]
    request.session = {}  # type: ignore[assignment]
    request._messages = FallbackStorage(request)  # type: ignore[attr-defined]
    protected_admin(People)(Person, admin.site).changelist_view(request)


# ---------------------------------------------------------------------- the editable list


def test_the_editable_list_leaves_an_account_holding_more_alone(make_user: MakeUser) -> None:
    """On Django 5.2 the list asked about the model, not each account: an e-mail is a way in."""
    manager = make_user('clearance.permission_view', 'clearance.permission_edit')
    peer = make_user()
    clerk = fresh(make_user(*PEOPLE), is_staff=True)

    saved_in_the_list(
        clerk,
        **{
            str(manager.pk): {'email': 'taken@over.example'},
            str(peer.pk): {'email': 'peer@new.example'},
        },
    )

    assert fresh(manager).email == ''
    assert fresh(peer).email == 'peer@new.example'


# ---------------------------------------------------------------------- their own account


def test_nobody_moves_themselves_to_other_rows_on_their_own_account(make_user: MakeUser) -> None:
    region_rule()
    clerk = fresh(make_user(*PEOPLE, *LOANS), is_staff=True, region='south')
    other = fresh(make_user(), region='south')
    model_admin = protected_admin(admin.ModelAdmin)(Person, admin.site)
    request = RequestFactory().get('/')
    request.user = clerk

    assert own_fields(clerk) == {'region'}
    assert 'region' in model_admin.get_readonly_fields(request, clerk)
    assert 'region' not in model_admin.get_readonly_fields(request, other)

    saved_in_the_list(
        clerk, **{str(clerk.pk): {'region': 'north'}, str(other.pk): {'region': 'north'}}
    )

    assert fresh(clerk).region == 'south'
    assert fresh(other).region == 'north'  # somebody else's, by somebody who may change them


def test_a_form_and_an_api_keep_what_a_persons_own_account_reaches(make_user: MakeUser) -> None:
    class PersonForm(ProtectedFieldsFormMixin, forms.ModelForm):  # type: ignore[type-arg]
        class Meta:
            model = Person
            fields = ('email', 'region')

    region_rule()
    clerk = fresh(make_user(*PEOPLE, *LOANS), region='south')
    other = make_user()
    owner = make_user(superuser=True)

    assert PersonForm(instance=clerk, user=clerk).fields['region'].disabled
    assert not PersonForm(instance=other, user=clerk).fields['region'].disabled
    assert list(
        refused_writes(clerk, Person, {'region': 'north', 'email': 'a@b.example'}, clerk)
    ) == ['region']
    assert refused_writes(clerk, Person, {'region': 'south'}, clerk) == {}  # sent back as it is
    assert refused_writes(clerk, Person, {'region': 'north'}, other) == {}
    assert refused_writes(owner, Person, {'region': 'north'}, owner) == {}  # reaches every row


def test_a_value_that_is_none_of_the_fields_is_not_what_the_account_holds(
    make_user: MakeUser,
) -> None:
    rule = ScopeRule(
        content_type=ContentType.objects.get_for_model(Loan),
        code='within_limit',
        name='Within their limit',
        match='all',
    )
    rule.conditions = [
        {'field': 'amount', 'operator': 'at_most', 'value': {'person': 'approval_limit'}}
    ]
    rule.save()
    officer = make_user(('lending.loan_view', 'within_limit'))

    assert list(refused_writes(officer, Person, {'approval_limit': 'no limit'}, officer)) == [
        'approval_limit'
    ]


# ---------------------------------------------------------------------- outranking


def test_a_scope_of_the_persons_own_is_not_held_by_holding_it_by_name(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    """Both hold ``loan_edit`` in "their region" - and each a region of their own."""
    region_rule()
    region_rule('north', person=False)
    policy = registry.policy_for(Person)
    south = fresh(make_user(*PEOPLE, *LOANS), region='south')
    north = fresh(make_user(*LOANS), region='north')

    assert outranks(north, south)
    assert not policy.allows(south, 'edit', north)

    # The same rows for anybody - a rule comparing with a constant - is held by holding it.
    fixed = (('lending.loan_view', 'north'), ('lending.loan_edit', 'north'))
    assert not outranks(make_user(*fixed), make_user(*PEOPLE, *fixed))
    # A scope in code is handed the person: theirs is not anybody else's.
    assert outranks(
        make_user(('lending.loan_view', 'own')), make_user(('lending.loan_view', 'own'))
    )
    # Holding it on every row is holding everybody's.
    assert not outranks(
        north, make_user(*PEOPLE, ('lending.loan_view', 'all'), ('lending.loan_edit', 'all'))
    )
    # With no scope chosen, it is the model's default that is compared: every row of a
    # statement, no loan at all, and a payment's "their own" - which is each one's own.
    assert not outranks(make_user('lending.view_statement'), make_user('lending.view_statement'))
    assert not outranks(make_user('lending.loan_view'), make_user('lending.loan_view'))
    assert outranks(make_user('lending.view_payment'), make_user('lending.view_payment'))
    # A field's permission is the person's, not the row's: no rows to differ by.
    score = 'lending.loan_view_credit_score'
    assert not outranks(make_user(score), make_user(score))


# ---------------------------------------------------------------------- what goes with a row


def test_deleting_an_account_takes_only_what_its_deleter_may_delete(make_user: MakeUser) -> None:
    person = make_user()
    Loan.objects.create(applicant=person, amount=1)
    remover = make_user(('accounts.delete_person', 'all'))

    with pytest.raises(PermissionDenied):
        require_deletable(remover, person)

    remover = make_user(('accounts.delete_person', 'all'), ('lending.loan_delete', 'all'))
    require_deletable(remover, person)
