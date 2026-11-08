"""
clearance_check says what only the database can tell is wrong - and fails on
what gives no access silently.

If these fail, a rule scope whose field was renamed reaches nothing and
nobody is told, a grant keeps a scope its model no longer offers, or a
permission nothing checks sits in the admin site looking like control.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import CommandError, call_command

from clearance.health import ERROR, WARNING, Finding, findings
from clearance.models import ProtectedField, ScopeGrant, ScopeRule, StatusAction
from tests.conftest import MakeBundle, MakeUser
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db


def check(verbosity: int = 1) -> str:
    out = StringIO()
    call_command('clearance_check', stdout=out, verbosity=verbosity)
    return out.getvalue()


def codes() -> list[str]:
    return [finding.code for finding in findings()]


def test_a_database_as_migrate_left_it_has_nothing_wrong() -> None:
    assert findings() == []
    assert 'Nothing is wrong.' in check()
    assert 'permission(s) nobody holds' in check(verbosity=2)


def test_a_rule_that_no_longer_checks_out_is_an_error() -> None:
    loans = ContentType.objects.get_for_model(Loan)
    ScopeRule.objects.create(
        content_type=loans,
        code='large',
        name='Large',
        conditions=[{'field': 'amount', 'operator': 'at_least', 'value': {'constant': 5}}],
    )
    ProtectedField.objects.create(content_type=loans, field='amount')

    (finding,) = findings()
    assert (finding.level, finding.code) == (ERROR, 'broken_rule')
    assert "'large'" in finding.message

    with pytest.raises(CommandError, match='1 error'):
        check()


def test_a_status_action_whose_field_or_values_are_gone_is_an_error() -> None:
    payments = ContentType.objects.get_for_model(Payment)
    StatusAction.objects.create(
        content_type=payments, code='void', name='Void', field='gone', to_values=['x']
    )
    StatusAction.objects.create(
        content_type=payments, code='lose', name='Lose', field='state', to_values=['lost']
    )

    messages = [finding.message for finding in findings()]

    assert any("writes 'gone', which is gone" in message for message in messages)
    assert any('holds no more: lost' in message for message in messages)


def test_a_grant_whose_scope_is_offered_no_more_is_an_error(make_bundle: MakeBundle) -> None:
    bundle = make_bundle({'lending.loan_view': 'own'}, name='Readers')
    ScopeGrant.objects.filter(group=bundle).update(scope='vanished')

    (finding,) = findings()
    assert (finding.level, finding.code) == (ERROR, 'lost_scope')
    assert 'reaches no rows' in finding.message


def test_a_grant_with_no_scope_where_the_default_reaches_nothing_is_a_warning(
    make_bundle: MakeBundle, make_user: MakeUser
) -> None:
    make_bundle({'lending.loan_view': None, 'lending.loan_view_credit_score': None}, name='Readers')
    make_user('lending.loan_edit')

    found = findings()
    assert {finding.code for finding in found} == {'scope_needed'}
    assert len(found) == 2, "a field's permission takes no scope, and is not asked for one"
    assert all(finding.level == WARNING for finding in found)
    assert 'Nothing is wrong.' not in check(), 'warned of, not failed on'


def test_a_permission_nothing_checks_is_a_warning() -> None:
    Permission.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), codename='loan_fly', name='Can fly'
    )

    assert codes() == ['unaccounted_permission']
    assert 'lending.loan_fly is checked by nothing' in check()


def test_errors_come_before_warnings(make_bundle: MakeBundle) -> None:
    Permission.objects.create(
        content_type=ContentType.objects.get_for_model(Loan), codename='loan_fly', name='Can fly'
    )
    bundle = make_bundle({'lending.loan_view': 'own'}, name='Readers')
    ScopeGrant.objects.filter(group=bundle).update(scope='vanished')

    assert [finding.level for finding in findings()] == [ERROR, WARNING]
    assert str(Finding(ERROR, 'x', 'Broken.')) == 'error: Broken.'


def test_a_grant_on_a_model_that_is_gone_is_not_this_checks_to_judge(
    make_bundle: MakeBundle,
) -> None:
    gone = ContentType.objects.create(app_label='lending', model='overdraft')
    permission = Permission.objects.create(content_type=gone, codename='overdraft_view', name='x')
    bundle = make_bundle({}, name='Old')
    bundle.permissions.add(permission)
    ScopeGrant.objects.create(group=bundle, permission=permission, scope='anything')

    assert findings() == []
