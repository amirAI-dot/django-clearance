"""
Every change to access goes through one service, which refuses the ones that
would let somebody give themselves everything.

If these fail, whoever may manage bundles makes one of every permission and
gives it to themselves, hands a colleague a wider scope than they hold so
the colleague can hand it back, or removes the last person able to manage
access - and nothing but the superuser can ever fix it.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.dispatch import Signal

from clearance import signals
from clearance.grants import grants_of
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeUser
from tests.project.accounts.models import Person

MANAGE = ('clearance.permission_create', 'clearance.permission_edit', 'clearance.permission_delete')


@pytest.fixture
def manager(make_user: MakeUser) -> Person:
    """Somebody who manages access and holds loan_view in every row, loan_edit in their own."""
    return make_user(
        *(name for name in MANAGE),
        ('lending.loan_view', 'all'),
        ('lending.loan_edit', 'own'),
    )


@pytest.fixture
def colleague(make_user: MakeUser) -> Person:
    """Somebody else who manages access - so a manager is never the last."""
    return make_user(*MANAGE)


@pytest.fixture
def access(manager: Person, colleague: Person) -> AccessService:
    return AccessService(actor=manager)


def fresh(person: Person) -> Person:
    return Person.objects.get(pk=person.pk)


Received = list[dict[str, Any]]


@pytest.fixture
def received() -> Iterator[Callable[[Signal], Received]]:
    """
    What a signal sends, caught. A signal is sent once its change commits, and a
    test's transaction never commits - so a test runs the commit callbacks
    itself, with ``django_capture_on_commit_callbacks``, where its change ends.
    """
    connected: list[tuple[Signal, Callable[..., None]]] = []

    def listen(signal: Signal) -> Received:
        caught: Received = []

        def receiver(**kwargs: Any) -> None:
            caught.append(kwargs)

        signal.connect(receiver, weak=False)
        connected.append((signal, receiver))
        return caught

    yield listen

    for signal, receiver in connected:
        signal.disconnect(receiver)


# ---------------------------------------------------------------- what the service does


def test_a_bundle_is_made_and_given_with_its_scopes(
    access: AccessService, make_user: MakeUser
) -> None:
    readers = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    person = make_user()
    access.give_bundle(person, readers)

    assert grants_of(fresh(person)).scopes('lending.loan_view') == {'all'}
    assert access.bundle_grants(readers) == {'lending.loan_view': 'all'}


def test_changing_a_bundle_changes_it_for_everybody_holding_it(
    access: AccessService, make_user: MakeUser
) -> None:
    bundle = access.create_bundle('Editors', {'lending.loan_view': 'all'})
    ana, bob = make_user(bundles=(bundle,)), make_user(bundles=(bundle,))
    access.change_bundle(bundle, grants={'lending.loan_view': 'all', 'lending.loan_edit': 'own'})

    assert fresh(ana).has_perm('lending.loan_edit')
    assert fresh(bob).has_perm('lending.loan_edit')


def test_revoking_takes_one_permission_from_one_person(
    access: AccessService, make_user: MakeUser
) -> None:
    bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    ana, bob = make_user(bundles=(bundle,)), make_user(bundles=(bundle,))
    access.revoke(ana, 'lending.loan_view', reason='Under review')

    assert not fresh(ana).has_perm('lending.loan_view')
    assert fresh(bob).has_perm('lending.loan_view')

    access.restore(ana, 'lending.loan_view')
    assert fresh(ana).has_perm('lending.loan_view')


def test_revoking_a_direct_grant_removes_it(access: AccessService, make_user: MakeUser) -> None:
    person = make_user()
    access.grant(person, 'lending.loan_view', 'all')
    access.revoke(person, 'lending.loan_view')

    assert not fresh(person).has_perm('lending.loan_view')


def test_a_person_changed_in_this_request_is_read_fresh(
    access: AccessService, make_user: MakeUser
) -> None:
    person = make_user()
    assert not person.has_perm('lending.loan_view')

    access.grant(person, 'lending.loan_view', 'all')

    assert person.has_perm('lending.loan_view'), 'the cache on the object was dropped'


def test_a_scope_the_model_does_not_offer_is_refused(access: AccessService) -> None:
    with pytest.raises(ValidationError, match='offers no scope'):
        access.create_bundle('Odd', {'lending.loan_view': 'everybody_else'})


def test_a_permission_nobody_created_is_refused(access: AccessService) -> None:
    with pytest.raises(ValidationError, match='no such permission'):
        access.create_bundle('Odd', {'lending.loan_fly': None})


def test_every_change_is_announced_once_it_commits(
    access: AccessService,
    make_user: MakeUser,
    manager: Person,
    received: Callable[[Signal], Received],
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    created, given = received(signals.bundle_created), received(signals.bundle_given)
    person = make_user()

    with django_capture_on_commit_callbacks(execute=True):
        bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
        access.give_bundle(person, bundle)
        assert created == [], 'nothing is announced before the change commits'

    assert created == [
        {
            'signal': signals.bundle_created,
            'sender': AccessService,
            'actor': manager,
            'bundle': bundle,
            'grants': {'lending.loan_view': 'all'},
        }
    ]
    assert [event['person'] for event in given] == [person]


def test_asking_for_what_is_already_so_changes_nothing(
    access: AccessService,
    make_user: MakeUser,
    received: Callable[[Signal], Received],
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    person = make_user(bundles=(bundle,))
    given, changed = received(signals.bundle_given), received(signals.bundle_changed)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        access.give_bundle(person, bundle)
        access.change_bundle(bundle, grants={'lending.loan_view': 'all'})

    assert callbacks == []

    assert given == []
    assert changed == []


def test_deleting_a_bundle_takes_what_it_gave_from_everybody_holding_it(
    access: AccessService,
    make_user: MakeUser,
    received: Callable[[Signal], Received],
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    person = make_user(bundles=(bundle,))
    deleted = received(signals.bundle_deleted)

    with django_capture_on_commit_callbacks(execute=True):
        access.delete_bundle(bundle)

    assert not fresh(person).has_perm('lending.loan_view')
    assert [event['people'] for event in deleted] == [[person]], 'the announcement says whom'


def test_taking_a_bundle_takes_what_it_gave(access: AccessService, make_user: MakeUser) -> None:
    bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    person = make_user(bundles=(bundle,))
    access.take_bundle(person, bundle)
    access.take_bundle(person, bundle)  # taking it again is not a change

    assert not fresh(person).has_perm('lending.loan_view')


def test_granting_again_with_another_scope_changes_the_scope(
    access: AccessService,
    make_user: MakeUser,
    received: Callable[[Signal], Received],
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    person = make_user()
    changed = received(signals.scope_changed)

    with django_capture_on_commit_callbacks(execute=True):
        access.grant(person, 'lending.loan_view', 'own')
        access.grant(person, 'lending.loan_view', 'reviewing')
        access.grant(person, 'lending.loan_view')

    assert [(event['before'], event['after']) for event in changed] == [
        ('own', 'reviewing'),
        ('reviewing', None),
    ]
    assert grants_of(fresh(person)).scopes('lending.loan_view') == {None}


def test_granting_what_was_taken_away_gives_it_back(
    access: AccessService, make_user: MakeUser
) -> None:
    bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    person = make_user(bundles=(bundle,))
    access.revoke(person, 'lending.loan_view')
    access.grant(person, 'lending.loan_view', 'all')

    assert fresh(person).has_perm('lending.loan_view')


def test_granting_what_is_already_held_the_same_way_changes_nothing(
    access: AccessService,
    make_user: MakeUser,
    received: Callable[[Signal], Received],
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    person = make_user()
    access.grant(person, 'lending.loan_view', 'own')
    granted, changed = received(signals.permission_granted), received(signals.scope_changed)

    with django_capture_on_commit_callbacks(execute=True):
        access.grant(person, 'lending.loan_view', 'own')

    assert granted == []
    assert changed == []


def test_grants_and_revocations_say_what_they_are(
    access: AccessService, make_user: MakeUser
) -> None:
    from clearance.models import PermissionRevocation, ScopeGrant

    person = make_user()
    access.grant(person, 'lending.loan_view', 'own')
    bundle = access.create_bundle('Readers', {'lending.loan_view': 'all'})
    person.groups.add(bundle)
    access.revoke(person, 'lending.loan_view')

    assert str(ScopeGrant.objects.get(group=bundle)) == 'Readers: loan_view in all'
    assert str(PermissionRevocation.objects.get()) == f'{person}: loan_view taken away'


def test_restoring_what_was_never_taken_changes_nothing(
    access: AccessService,
    make_user: MakeUser,
    received: Callable[[Signal], Received],
    django_capture_on_commit_callbacks: Callable[..., Any],
) -> None:
    restored = received(signals.permission_restored)

    with django_capture_on_commit_callbacks(execute=True):
        access.restore(make_user(), 'lending.loan_view')

    assert restored == []


def test_a_model_with_no_scopes_offers_only_every_row(
    access: AccessService, make_user: MakeUser, manager: Person
) -> None:
    root = AccessService(actor=None)

    with pytest.raises(ValidationError, match="offers no scope 'own'"):
        root.grant(make_user(), 'accounts.view_person', 'own')

    root.grant(make_user(), 'accounts.view_person', 'all')


# ---------------------------------------------------------------- the safety rules


def test_managing_access_needs_its_own_permission(make_user: MakeUser) -> None:
    access = AccessService(actor=make_user(('lending.loan_view', 'all')))

    with pytest.raises(AccessRefused) as refused:
        access.create_bundle('Readers', {'lending.loan_view': 'all'})

    assert refused.value.rule == 'may_not_manage'


def test_nobody_changes_their_own_access(access: AccessService, manager: Person) -> None:
    bundle = Group.objects.create(name='Anything')

    for change in (
        lambda: access.give_bundle(manager, bundle),
        lambda: access.grant(manager, 'lending.loan_view', 'all'),
        lambda: access.revoke(manager, 'lending.loan_view'),
    ):
        with pytest.raises(AccessRefused) as refused:
            change()
        assert refused.value.rule == 'own_access'


def test_nobody_changes_a_bundle_they_hold(access: AccessService, manager: Person) -> None:
    bundle = AccessService(actor=None).create_bundle('Theirs', {'lending.loan_view': 'all'})
    manager.groups.add(bundle)

    with pytest.raises(AccessRefused) as refused:
        access.change_bundle(
            bundle, grants={'lending.loan_view': 'all', 'lending.loan_edit': 'own'}
        )

    assert refused.value.rule == 'own_bundle'
    access.change_bundle(bundle, name='Renamed')  # renaming changes nobody's access
    assert Group.objects.get(pk=bundle.pk).name == 'Renamed'


def test_nobody_gives_what_they_do_not_hold(access: AccessService, make_user: MakeUser) -> None:
    for change in (
        lambda: access.create_bundle('Approvers', {'lending.loan_approve': 'all'}),
        lambda: access.grant(make_user(), 'lending.loan_approve', 'all'),
    ):
        with pytest.raises(AccessRefused) as refused:
            change()
        assert refused.value.rule == 'not_held'


def test_nobody_gives_a_bundle_holding_what_they_do_not_hold(
    access: AccessService, make_user: MakeUser
) -> None:
    approvers = AccessService(actor=None).create_bundle(
        'Approvers', {'lending.loan_approve': 'all'}
    )

    with pytest.raises(AccessRefused) as refused:
        access.give_bundle(make_user(), approvers)

    assert refused.value.rule == 'not_held'


def test_nobody_gives_a_wider_scope_than_they_hold(
    access: AccessService, make_user: MakeUser
) -> None:
    with pytest.raises(AccessRefused) as refused:
        access.grant(make_user(), 'lending.loan_edit', 'all')

    assert refused.value.rule == 'scope_not_held'
    access.grant(make_user(), 'lending.loan_edit', 'own')  # the scope they hold it with


def test_holding_every_row_lets_any_scope_be_given(
    access: AccessService, make_user: MakeUser
) -> None:
    access.grant(make_user(), 'lending.loan_view', 'reviewing')


def test_nobody_leaves_nobody_able_to_manage_access(make_user: MakeUser) -> None:
    root = make_user(superuser=True)
    last = make_user(*MANAGE)
    access = AccessService(actor=root)

    with pytest.raises(AccessRefused) as refused:
        access.revoke(last, 'clearance.permission_edit')

    assert refused.value.rule == 'nobody_left'
    assert fresh(last).has_perm('clearance.permission_edit'), 'the change was rolled back'


def test_the_superuser_and_the_system_answer_only_to_the_last_rule(
    make_user: MakeUser, colleague: Person
) -> None:
    root = make_user(superuser=True)

    AccessService(actor=root).grant(make_user(), 'lending.loan_approve', 'all')
    held = AccessService(actor=None).create_bundle('Everything', {'lending.loan_approve': 'all'})
    root.groups.add(held)
    AccessService(actor=root).change_bundle(held, grants={'lending.loan_view': 'all'})
