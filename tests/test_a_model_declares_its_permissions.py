"""
A resource declares its permissions on its model, and migrate creates them.

If these fail, a permission a policy asks for is missing from the database -
so nobody can ever be given it - or its name changes with the language the
project happened to start in, and makemigrations reports changes to models
nobody touched.
"""

import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from clearance.permissions import (
    DEFAULT_ACTIONS,
    RECORD_ACTIONS,
    PermissionSet,
    build_permissions,
)


def test_the_standard_actions_are_view_create_edit_and_delete() -> None:
    assert build_permissions('loan', 'loans') == (
        ('loan_view', 'Can view loans'),
        ('loan_create', 'Can create loans'),
        ('loan_edit', 'Can edit loans'),
        ('loan_delete', 'Can delete loans'),
    )


def test_a_record_is_never_given_a_delete_permission() -> None:
    assert 'delete' not in RECORD_ACTIONS
    assert set(RECORD_ACTIONS) < set(DEFAULT_ACTIONS)


def test_an_action_with_no_label_reads_as_its_own_words() -> None:
    assert build_permissions('loan', 'loans', actions=('look_up',)) == (
        ('loan_look_up', 'Can look up loans'),
    )


def test_a_label_of_its_own_replaces_the_standard_one() -> None:
    entries = build_permissions(
        'loan', 'loans', actions=('view',), labels={'view': 'Can read %(resource)s'}
    )

    assert entries == (('loan_view', 'Can read loans'),)


def test_the_stored_name_is_english_whatever_language_is_active() -> None:
    resource = _('user')  # a word Django's own catalogue translates

    with translation.override('fa'):
        assert str(resource) != 'user', 'the test needs a word that is translated'
        entries = build_permissions('member', resource, actions=('view',))

    assert entries == (('member_view', 'Can view user'),)


def test_the_label_is_said_in_the_active_language() -> None:
    permissions = PermissionSet('member', _('user'), actions=('view',))

    with translation.override('fa'):
        translated = permissions.label('view')

    assert translated != permissions.stored_name('view')
    assert permissions.stored_name('view') == 'Can view user'


@pytest.mark.parametrize(
    ('codename', 'actions'),
    [
        ('Loan', ('view',)),
        ('loan item', ('view',)),
        ('loan.item', ('view',)),
        ('loan_', ('view',)),
        ('loan', ()),
        ('loan', ('View',)),
        ('loan', ('look up',)),
    ],
)
def test_a_name_no_permission_could_be_built_from_is_refused(
    codename: str, actions: tuple[str, ...]
) -> None:
    with pytest.raises(ImproperlyConfigured):
        build_permissions(codename, 'loans', actions=actions)


def test_an_action_declared_twice_is_refused() -> None:
    with pytest.raises(ImproperlyConfigured, match='view'):
        build_permissions('loan', 'loans', actions=('view', 'edit', 'view'))


def test_a_label_for_an_action_not_declared_is_refused() -> None:
    with pytest.raises(ImproperlyConfigured, match='approve'):
        build_permissions('loan', 'loans', actions=('view',), labels={'approve': 'Can approve'})


@pytest.mark.django_db
def test_migrate_creates_exactly_the_declared_permissions() -> None:
    stored = dict(
        Permission.objects.filter(
            content_type__app_label='lending', content_type__model='loan'
        ).values_list('codename', 'name')
    )

    assert stored == {
        'loan_view': 'Can view loans',
        'loan_create': 'Can create loans',
        'loan_edit': 'Can edit loans',
        'loan_delete': 'Can delete loans',
        'loan_approve': 'Can approve or decline loans',
        'loan_look_up': 'Can look up loans',
        'loan_view_credit_score': 'Can view credit score of loans',
        'loan_edit_credit_score': 'Can edit credit score of loans',
        'loan_export': 'Can export loans',  # found on a function view, made by migrate
        'loan_remind': 'Can remind loans',  # found on a viewset's @action
        'loan_report': 'Can report loans',  # found on an APIView's policy_action
    }


@pytest.mark.django_db
def test_a_model_that_declares_nothing_keeps_djangos_own_four() -> None:
    stored = set(
        Permission.objects.filter(
            content_type__app_label='lending', content_type__model='payment'
        ).values_list('codename', flat=True)
    )

    assert stored == {'view_payment', 'add_payment', 'change_payment', 'delete_payment'}
