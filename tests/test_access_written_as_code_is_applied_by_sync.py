"""
Access written in the ACCESS file is applied by clearance_sync - shown first,
checked in CI, applied in one transaction - and read only everywhere else.

If these fail, a deployment's access drifts from the file in git without CI
noticing, a sync deletes a bundle an administrator made, a half-applied sync
leaves nobody able to manage access, or an administrator changes in the admin
site what the next sync silently puts back.
"""

from io import StringIO
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import CommandError, call_command
from django.test import Client, override_settings

from clearance import declared
from clearance.checks import check_access
from clearance.declared import Change, Sync, is_test_database, read_access, sync_after_migrate
from clearance.models import Declared, StatusAction
from clearance.roles.models import Role
from clearance.roles.services import RoleService
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeBundle, MakeUser
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan, Payment

pytestmark = pytest.mark.django_db

HERE = 'tests.test_access_written_as_code_is_applied_by_sync'

FULL = {
    'bundles': {
        'Clerks': {'lending.loan_view': 'all', 'lending.loan_edit': None},
        'Managers': {'clearance.permission_edit': None},
    },
    'status_actions': {
        'lending.Payment': {'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']}},
    },
    'roles': {
        'clerk': {'name': 'Clerk', 'ceiling': ['lending.loan_view'], 'bundles': ['Clerks']},
    },
}

CHANGED = {
    'bundles': {
        'Clerks': {'lending.loan_view': 'own', 'lending.loan_delete': None},
        'Managers': {'clearance.permission_edit': None},
    },
    'status_actions': {
        'lending.Payment': {
            'refund': {'field': 'state', 'to': ['refunded', 'due'], 'name': 'Give back'},
        },
    },
    'roles': {
        'clerk': {'name': 'Loan clerk', 'ceiling': None, 'bundles': []},
    },
}

NOTHING: dict[str, Any] = {}
NOT_A_DICTIONARY = ['bundles']
UNKNOWN_SECTION = {'people': {}}
NO_SUCH_PERMISSION = {'bundles': {'Odd': {'lending.loan_fly': None}}}
NO_SUCH_SCOPE = {'bundles': {'Odd': {'lending.loan_view': 'everywhere'}}}
NO_SUCH_BUNDLE = {'roles': {'clerk': {'bundles': ['Ghosts']}}}
NEW_FIELD = {
    'status_actions': {'lending.Loan': {'sign_off': {'field': 'status', 'to': ['approved']}}},
}
SHAPES = {
    'bundles': {'': {}, 'Lists': ['lending.loan_view'], 'Odd': {'loan_view': 1, 'nowhere.x': None}},
    'status_actions': {'lending.Ghost': {}, 'lending.Loan': [], 'lending.Payment': {'x': 'y'}},
    'roles': {
        'Clerk!': {},
        'clerk': {'colour': 'red'},
        'a': {'ceiling': 'x'},
        'b': {'bundles': 'x'},
    },
}
BAD_SECTIONS = {'bundles': [], 'status_actions': [], 'roles': []}


def access(name: str) -> Any:
    return override_settings(CLEARANCE={'ACCESS': f'{HERE}.{name}'})


def sync(*args: str) -> str:
    out = StringIO()
    call_command('clearance_sync', *args, stdout=out)
    return out.getvalue()


def lines(changes: list[Change]) -> list[str]:
    return [str(change).splitlines()[0] for change in changes]


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    make_user('clearance.permission_edit')
    return make_user(
        'clearance.permission_view',
        'clearance.permission_create',
        'clearance.permission_edit',
        'clearance.permission_delete',
        'clearance.role_ceiling_edit',
        superuser=False,
    )


# ---------------------------------------------------------------- reading the file


def test_no_file_named_is_no_file_to_sync() -> None:
    assert read_access() is None
    assert check_access() == []

    with pytest.raises(CommandError, match='names no file'):
        sync()


@pytest.mark.parametrize(
    ('name', 'message'),
    [
        ('MISSING', 'cannot be read'),
        ('NOT_A_DICTIONARY', 'is not a dictionary'),
        ('UNKNOWN_SECTION', 'sections no installed app reads: people'),
    ],
)
def test_a_file_that_cannot_be_read_is_refused_at_start_up(name: str, message: str) -> None:
    with access(name):
        errors = check_access()

        with pytest.raises(CommandError, match=message):
            sync()

    assert [error.id for error in errors] == ['clearance.E001']
    assert message in errors[0].msg


def test_a_file_saying_what_cannot_be_is_refused_at_start_up() -> None:
    with access('SHAPES'):
        messages = [error.msg for error in check_access()]

    assert {error for error in messages if 'is not a bundle name' in error}
    assert any("'Lists' is a dictionary of permissions" in m for m in messages)
    assert any("'loan_view' is not app_label.codename" in m for m in messages)
    assert any("'nowhere.x' names no installed app" in m for m in messages)
    assert any('a scope is a name, or None' in m for m in messages)
    assert any("'lending.Ghost' is not an installed model" in m for m in messages)
    assert any("'lending.Loan' is a dictionary of codes" in m for m in messages)
    assert any("lending.Payment.x: give it 'field'" in m for m in messages)
    assert any("'Clerk!' is not a code" in m for m in messages)
    assert any("'clerk': give it 'name'" in m for m in messages)
    assert any("'ceiling' is a list of permissions" in m for m in messages)
    assert any("'bundles' is a list of bundle names" in m for m in messages)


def test_a_section_of_the_wrong_kind_is_refused() -> None:
    with access('BAD_SECTIONS'):
        messages = [error.msg for error in check_access()]

    assert len(messages) == 3


def test_the_project_file_reads(settings: Any) -> None:
    with access('FULL'):
        assert check_access() == []


# ---------------------------------------------------------------- applying it


def test_a_sync_makes_what_the_file_declares_and_says_so() -> None:
    with access('FULL'):
        out = sync()

    assert "+ bundle 'Clerks'" in out
    assert "+ status action 'lending.Payment.refund'" in out
    assert "+ role 'clerk'" in out
    assert AccessService(actor=None).bundle_grants(Group.objects.get(name='Clerks')) == {
        'lending.loan_view': 'all',
        'lending.loan_edit': None,
    }
    assert StatusAction.objects.get(code='refund').to_values == ['refunded']
    role = Role.objects.get(code='clerk')
    assert RoleService(actor=None).ceiling_of(role) == {'lending.loan_view'}
    assert list(role.bundles.values_list('group__name', flat=True)) == ['Clerks']
    assert Declared.keys('bundle') == {'Clerks', 'Managers'}


def test_a_second_sync_finds_nothing_to_change() -> None:
    with access('FULL'):
        sync()
        assert 'holds what ACCESS declares' in sync()
        sync('--check')


def test_a_sync_changes_what_the_file_changes() -> None:
    with access('FULL'):
        sync()

    with access('CHANGED'):
        out = sync()

    assert "~ bundle 'Clerks'" in out
    assert '+ lending.loan_delete' in out
    assert '~ lending.loan_view: all -> own' in out
    assert '- lending.loan_edit' in out
    assert AccessService(actor=None).bundle_grants(Group.objects.get(name='Clerks')) == {
        'lending.loan_view': 'own',
        'lending.loan_delete': None,
    }
    action = StatusAction.objects.get(code='refund')
    assert (action.name, action.to_values, action.from_values) == (
        'Give back',
        ['refunded', 'due'],
        [],
    )
    role = Role.objects.get(code='clerk')
    assert (role.name, role.limited, role.bundles.count()) == ('Loan clerk', False, 0)


def test_what_the_file_no_longer_names_is_deleted_and_nothing_else(
    make_bundle: MakeBundle,
) -> None:
    make_bundle({'lending.loan_view': 'all'}, name='Made in the admin site')

    with access('FULL'):
        sync()

    with access('NOTHING'):
        out = sync()

    assert "- bundle 'Clerks'" in out
    assert "- role 'clerk'" in out
    assert "- status action 'lending.Payment.refund'" in out
    assert list(Group.objects.values_list('name', flat=True)) == ['Made in the admin site']
    assert not Role.objects.exists()
    assert not StatusAction.objects.exists()
    assert not Declared.objects.exists()


def test_a_bundle_made_in_the_admin_site_is_taken_over_once_the_file_names_it(
    make_bundle: MakeBundle,
) -> None:
    make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': None}, name='Clerks')
    Role.objects.create(code='clerk', name='Clerk')

    with access('FULL'):
        out = sync()

    assert out.count('now declared in code') == 2
    assert Declared.holds('bundle', 'Clerks')
    assert Declared.holds('role', 'clerk')


def test_a_status_action_made_in_the_admin_site_is_taken_over_too() -> None:
    AccessService(actor=None).create_status_action(
        Payment, 'refund', 'Refund', 'state', ['refunded'], ['paid']
    )

    with access('FULL'):
        plan = Sync(read_access() or {}).plan()

    (refund,) = [change for change in plan if change.kind == 'status_action']
    assert (refund.verb, refund.details) == ('~', ('now declared in code',))


@pytest.mark.parametrize(
    ('name', 'message'),
    [
        ('NO_SUCH_PERMISSION', 'lending.loan_fly: no such permission'),
        ('NO_SUCH_SCOPE', "its model offers no scope 'everywhere'"),
        ('NO_SUCH_BUNDLE', "there is no bundle 'Ghosts'"),
    ],
)
def test_a_file_the_database_cannot_hold_is_refused_whole(name: str, message: str) -> None:
    with access(name), pytest.raises(CommandError, match=message):
        sync('--dry-run')

    assert not Group.objects.exists()


def test_a_status_action_keeps_its_field() -> None:
    AccessService(actor=None).create_status_action(Loan, 'sign_off', 'Sign off', 'approved', [True])

    with access('NEW_FIELD'), pytest.raises(CommandError, match='keeps its field'):
        sync()


def test_a_sync_the_safety_rules_refuse_changes_nothing(make_user: MakeUser) -> None:
    with access('FULL'):
        sync()

    make_user(bundles=(Group.objects.get(name='Managers'),))
    Group.objects.get(name='Clerks').delete()  # so the next sync would make it again

    with access('NOTHING'), pytest.raises(CommandError, match='Nothing was changed'):
        sync()

    assert Group.objects.filter(name='Managers').exists(), 'the last manager kept their bundle'


# ---------------------------------------------------------------- showing it first


def test_a_dry_run_says_what_would_change_and_writes_nothing() -> None:
    with access('FULL'):
        out = sync('--dry-run')

    assert "+ bundle 'Clerks'" in out
    assert 'nothing was written' in out
    assert not Group.objects.exists()


def test_a_check_fails_while_the_database_differs_from_the_file() -> None:
    with access('FULL'), pytest.raises(CommandError, match='differs from ACCESS by 4'):
        sync('--check')


def test_a_change_reads_as_one_line_and_its_details() -> None:
    change = Change('~', 'status_action', 'lending.Payment.refund', ('to: a -> b',))

    assert str(change) == "~ status action 'lending.Payment.refund'\n    to: a -> b"


# ---------------------------------------------------------------- read only elsewhere


def test_what_the_file_owns_is_refused_to_anybody_but_the_sync(
    manager: Person, make_user: MakeUser
) -> None:
    with access('FULL'):
        sync()

    clerks = Group.objects.get(name='Clerks')
    role = Role.objects.get(code='clerk')
    refund = StatusAction.objects.get(code='refund')

    acts = (
        lambda actor: AccessService(actor=actor).change_bundle(clerks, name='Other'),
        lambda actor: AccessService(actor=actor).delete_bundle(clerks),
        lambda actor: AccessService(actor=actor).change_status_action(refund, name='Other'),
        lambda actor: AccessService(actor=actor).delete_status_action(refund),
        lambda actor: RoleService(actor=actor).rename_role(role, 'Other'),
        lambda actor: RoleService(actor=actor).set_ceiling(role, None),
    )

    for actor in (manager, make_user(superuser=True)):
        for act in acts:
            with pytest.raises(AccessRefused) as refusal:
                act(actor)
            assert refusal.value.rule == 'declared'

    AccessService(actor=None).change_bundle(clerks, name='Clerks')


def test_the_pages_show_it_read_only(client: Client, manager: Person) -> None:
    with access('FULL'):
        sync()

    manager.is_staff = True
    manager.save()
    client.force_login(manager)
    clerks = Group.objects.get(name='Clerks')
    role = Role.objects.get(code='clerk')

    bundle_page = client.get(f'/admin/access/bundles/{clerks.pk}/').content.decode()
    assert 'Declared in code' in bundle_page
    assert 'value="Save"' not in bundle_page
    assert 'declared in code' in client.get('/admin/access/bundles/').content.decode()

    role_page = client.get(f'/admin/access/roles/{role.pk}/').content.decode()
    assert 'Declared in code' in role_page
    assert 'Save the ceiling' not in role_page
    assert 'declared in code' in client.get('/admin/access/roles/').content.decode()


# ---------------------------------------------------------------- on migrate


def migrated(sender: Any, **kwargs: Any) -> None:
    sync_after_migrate(sender=sender, **{'using': 'default', 'plan': [], 'verbosity': 0, **kwargs})


@pytest.fixture
def real_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(declared, 'is_test_database', lambda using: False)


def last_app() -> Any:
    from django.apps import apps

    return list(apps.get_app_configs())[-1]


def test_migrate_applies_the_file_when_asked_to(real_database: None, capsys: Any) -> None:
    with override_settings(CLEARANCE={'ACCESS': f'{HERE}.FULL', 'SYNC_ON_MIGRATE': True}):
        migrated(last_app(), verbosity=1)

    assert Group.objects.filter(name='Clerks').exists()
    assert '4 change(s) applied' in capsys.readouterr().out


@pytest.mark.parametrize(
    ('setting', 'when'),
    [
        ({'ACCESS': f'{HERE}.FULL'}, {}),
        ({'SYNC_ON_MIGRATE': True}, {}),
        ({'ACCESS': f'{HERE}.FULL', 'SYNC_ON_MIGRATE': True}, {'first': True}),
        ({'ACCESS': f'{HERE}.FULL', 'SYNC_ON_MIGRATE': True}, {'using': 'other'}),
        ({'ACCESS': f'{HERE}.FULL', 'SYNC_ON_MIGRATE': True}, {'plan': [(None, True)]}),
    ],
    ids=['not asked', 'no file', 'not the last app', 'not the default database', 'backwards'],
)
def test_migrate_leaves_access_alone_otherwise(
    real_database: None, setting: dict[str, Any], when: dict[str, Any]
) -> None:
    from django.apps import apps

    sender = next(iter(apps.get_app_configs())) if when.pop('first', False) else last_app()

    with override_settings(CLEARANCE=setting):
        migrated(sender, **when)

    assert not Group.objects.exists()


def test_migrate_never_syncs_a_test_database() -> None:
    with override_settings(CLEARANCE={'ACCESS': f'{HERE}.FULL', 'SYNC_ON_MIGRATE': True}):
        migrated(last_app())

    assert not Group.objects.exists()


@pytest.mark.parametrize(
    ('settings_dict', 'test'),
    [
        ({'NAME': 'file:memorydb_default?mode=memory&cache=shared', 'TEST': {}}, True),
        ({'NAME': ':memory:', 'TEST': {}}, True),
        ({'NAME': 'test_shop', 'TEST': {}}, True),
        ({'NAME': 'shop_ci', 'TEST': {'NAME': 'shop_ci'}}, True),
        ({'NAME': 'shop', 'TEST': {}}, False),
    ],
)
def test_a_test_database_is_told_by_its_name(
    monkeypatch: pytest.MonkeyPatch, settings_dict: dict[str, Any], test: bool
) -> None:
    monkeypatch.setattr(
        declared, 'connections', {'x': SimpleNamespace(settings_dict=settings_dict)}
    )

    assert is_test_database('x') is test


def test_the_file_may_name_a_ceiling_of_nothing_by_leaving_it_out() -> None:
    from clearance.roles.declared import RoleSection

    with pytest.raises(ValidationError, match="there is no bundle 'Ghosts'"):
        RoleSection().changes({'clerk': {'bundles': ['Ghosts']}}, {})

    upserts, _ = RoleSection().changes({'clerk': {}}, {})
    assert lines(upserts) == ["+ role 'clerk'"]
    assert upserts[0].details == ('ceiling: nothing', 'bundles: none')


def test_unreadable_names_are_impossible_to_read() -> None:
    with access('MISSING'), pytest.raises(ImproperlyConfigured):
        read_access()


# ---------------------------------------------------------------- the edges


def test_a_sync_refuses_a_file_saying_what_cannot_be_before_asking_the_database() -> None:
    with pytest.raises(ValidationError, match='is not a bundle name'):
        Sync(SHAPES).plan()


def test_what_was_deleted_by_hand_is_simply_let_go() -> None:
    with access('FULL'):
        sync()

    StatusAction.objects.all().delete()
    Role.objects.all().delete()

    with access('NOTHING'):
        sync()

    assert not Declared.objects.exists()


def test_a_quiet_migrate_applies_without_a_word(real_database: None, capsys: Any) -> None:
    with override_settings(CLEARANCE={'ACCESS': f'{HERE}.FULL', 'SYNC_ON_MIGRATE': True}):
        migrated(last_app(), verbosity=0)

    assert Group.objects.filter(name='Clerks').exists()
    assert capsys.readouterr().out == ''


def test_a_role_ceiling_naming_no_permission_is_refused() -> None:
    from clearance.roles.declared import RoleSection

    with pytest.raises(ValidationError, match=r"role 'clerk': no\.such: no such permission"):
        RoleSection().changes({'clerk': {'ceiling': ['no.such']}}, {})


def test_a_role_whose_ceiling_alone_changes_says_only_that() -> None:
    from clearance.roles.declared import RoleSection

    with access('FULL'):
        sync()

    upserts, _ = RoleSection().changes(
        {'clerk': {'name': 'Clerk', 'ceiling': None, 'bundles': ['Clerks']}}, FULL
    )

    assert [change.details for change in upserts] == [('ceiling: lending.loan_view -> none',)]

    renamed, _ = RoleSection().changes(
        {'clerk': {'name': 'Loan clerk', 'ceiling': ['lending.loan_view'], 'bundles': ['Clerks']}},
        FULL,
    )
    assert [change.details for change in renamed] == [("name: 'Clerk' -> 'Loan clerk'",)]


def test_what_the_file_owns_says_what_it_is() -> None:
    assert str(Declared(kind='bundle', key='Clerks')) == 'bundle: Clerks'


def test_a_real_migrate_applies_the_file_once_every_permission_exists(tmp_path: Any) -> None:
    """The whole way: migrate makes the permissions, then the sync gives access."""
    import os
    import sqlite3
    import subprocess
    import sys
    from contextlib import closing

    database = tmp_path / 'project.sqlite3'
    done = subprocess.run(
        [sys.executable, '-m', 'django', 'migrate', '--settings=tests.project.sync_settings'],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, 'PYTHONPATH': '.', 'CLEARANCE_SYNC_DATABASE': str(database)},
    )

    assert done.returncode == 0, done.stdout + done.stderr
    assert '4 change(s) applied from ACCESS' in done.stdout

    with closing(sqlite3.connect(database)) as connection:  # a with block alone leaves it open
        bundles = {name for (name,) in connection.execute('SELECT name FROM auth_group')}

    assert bundles == {'Clerks', 'Managers'}
