"""
A permission, a bundle or a role reads in the reader's language - the name
an administrator gave in it, else what the code says in it, else its row.

If these fail, a Persian administrator chooses what to give from names they
cannot read, a name given in one language shows in another, a name outlives
the bundle it named, or a page reading names costs a query per name.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import Client, override_settings
from pytest_django import DjangoAssertNumQueries

from clearance.labels import Labels, install_labels, label_of, labels_in, uninstall_labels
from clearance.permissions import declared_label
from clearance.roles.models import Role
from clearance.safety import AccessRefused
from clearance.translations import signals
from clearance.translations.checks import order_errors
from clearance.translations.labels import TranslatedLabels, languages_for
from clearance.translations.models import Translation
from clearance.translations.services import TranslationService
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan

pytestmark = pytest.mark.django_db

#: "Branch managers", in Persian - written as escapes: the code is English only.
MANAGERS_FA = 'مدیران شعبه'
#: "Approve", in Persian.
APPROVE_FA = 'تأیید'


@pytest.fixture
def managers(make_bundle: MakeBundle) -> Group:
    return make_bundle({'lending.loan_view': 'all'}, name='Branch managers')


@pytest.fixture
def editor(make_user: MakeUser) -> Person:
    make_user('clearance.permission_edit')  # somebody else who manages access
    person = make_user('clearance.permission_view', 'clearance.permission_edit')
    person.is_staff = True
    person.save()
    return Person.objects.get(pk=person.pk)


def name(thing: Any, language: str, words: str, description: str = '') -> None:
    TranslationService(actor=None).name(thing, language, words, description)


# ---------------------------------------------------------------- without names given


def test_a_permission_declared_in_code_reads_as_the_code_says(managers: Group) -> None:
    assert label_of(permission('lending.loan_approve')) == 'Can approve or decline loans'
    assert (
        label_of(permission('lending.loan_view_credit_score')) == 'Can view credit score of loans'
    )
    assert label_of(permission('lending.view_payment')) == 'Can view payment', "Django's own"
    assert label_of(managers) == 'Branch managers'
    assert label_of(Role.objects.create(code='clerk', name='Clerk')) == 'Clerk'


def test_what_the_code_says_is_read_in_the_language_asked_for() -> None:
    assert declared_label(Loan, 'loan_approve') == 'Can approve or decline loans'
    assert declared_label(Loan, 'nothing_like_it') is None
    assert labels_in('fa').of(permission('lending.loan_approve')) == 'Can approve or decline loans'


# ---------------------------------------------------------------- names given


def test_a_name_given_in_a_language_is_read_in_it(managers: Group) -> None:
    name(managers, 'fa', MANAGERS_FA, 'They run a branch.')

    assert labels_in('fa').of(managers) == MANAGERS_FA
    assert labels_in('fa').description_of(managers) == 'They run a branch.'
    assert labels_in('en').of(managers) == 'Branch managers'
    assert labels_in('en').description_of(managers) == ''


def test_a_regional_language_reads_its_own_name_then_its_bases(managers: Group) -> None:
    name(managers, 'fa', MANAGERS_FA)

    assert labels_in('fa-ir').of(managers) == MANAGERS_FA

    Translation.objects.create(
        content_type=ContentType.objects.get_for_model(Group),
        object_pk=str(managers.pk),
        language='fa-ir',
        name='Regional',
    )
    assert labels_in('fa-ir').of(managers) == 'Regional'
    assert languages_for('fa') == ['fa']


def test_permissions_and_roles_are_named_the_same_way() -> None:
    approve = permission('lending.loan_approve')
    role = Role.objects.create(code='clerk', name='Clerk')
    name(approve, 'fa', APPROVE_FA)
    name(role, 'fa', 'Karmand')

    labels = labels_in('fa')
    assert (labels.of(approve), labels.of(role)) == (APPROVE_FA, 'Karmand')


def test_the_names_of_a_language_are_read_once(
    managers: Group, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    name(managers, 'fa', MANAGERS_FA)
    approve = Permission.objects.select_related('content_type').get(codename='loan_approve')
    ContentType.objects.get_for_model(Group)
    ContentType.objects.get_for_model(approve)
    labels = labels_in('fa')

    with django_assert_num_queries(1):
        labels.of(managers)
        labels.of(approve)
        labels.description_of(managers)


def test_something_unsaved_has_no_name_but_its_own(managers: Group) -> None:
    assert labels_in('fa').of(Group(name='Not yet')) == 'Not yet'


def test_a_name_goes_with_what_it_names(managers: Group) -> None:
    name(managers, 'fa', MANAGERS_FA)
    managers.delete()

    assert not Translation.objects.exists()
    Translation.objects.create(
        content_type=ContentType.objects.get_for_model(Group),
        object_pk='1',
        language='fa',
        name='x',
    ).delete()


# ---------------------------------------------------------------- giving names


def test_naming_needs_the_permission_to_edit_access(managers: Group, make_user: MakeUser) -> None:
    with pytest.raises(AccessRefused):
        TranslationService(actor=make_user('clearance.permission_view')).name(
            managers, 'fa', MANAGERS_FA
        )


def test_a_name_is_given_only_in_a_language_the_project_speaks(managers: Group) -> None:
    with pytest.raises(ValidationError, match="'de' is not one of LANGUAGES: en, fa"):
        name(managers, 'de', 'Filialleiter')


def test_an_empty_name_takes_the_name_away_and_every_change_is_announced(
    managers: Group, django_capture_on_commit_callbacks: Callable[..., Any]
) -> None:
    caught: list[tuple[Any, Any]] = []

    def receiver(**kwargs: Any) -> None:
        caught.append((kwargs['before'], kwargs['after']))

    signals.name_changed.connect(receiver, weak=False)

    try:
        with django_capture_on_commit_callbacks(execute=True):
            name(managers, 'fa', MANAGERS_FA)
            name(managers, 'fa', MANAGERS_FA)  # no change: nothing sent
            name(managers, 'fa', '  ')
    finally:
        signals.name_changed.disconnect(receiver)

    assert caught == [(None, (MANAGERS_FA, '')), ((MANAGERS_FA, ''), None)]
    assert not Translation.objects.exists()


# ---------------------------------------------------------------- the pages


def test_the_names_page_names_a_thing_in_every_language(
    client: Client, editor: Person, managers: Group
) -> None:
    client.force_login(editor)
    address = f'/admin/access/names/auth.group/{managers.pk}/'

    assert [code for code, _, _ in client.get(address).context['rows']] == ['en', 'fa']
    client.post(address, {'name:fa': MANAGERS_FA, 'description:fa': 'Branches', 'name:en': ''})

    assert labels_in('fa').of(managers) == MANAGERS_FA
    assert client.get(address).context['rows'][1][2].description == 'Branches'


@pytest.mark.parametrize(
    'address',
    [
        '/admin/access/names/auth.user/1/',
        '/admin/access/names/auth.group/999999/',
        '/admin/access/names/auth.group/not-a-number/',
    ],
)
def test_the_names_page_of_nothing_namable_is_not_found(
    client: Client, editor: Person, address: str
) -> None:
    client.force_login(editor)

    assert client.get(address).status_code == 404


def test_naming_on_the_page_obeys_the_rules(
    client: Client, managers: Group, make_user: MakeUser
) -> None:
    viewer = make_user('clearance.permission_view')
    viewer.is_staff = True
    viewer.save()
    client.force_login(viewer)

    response = client.post(
        f'/admin/access/names/auth.group/{managers.pk}/', {'name:fa': 'x'}, follow=True
    )

    assert [str(message) for message in response.context['messages']] == [
        'You may not edit access.'
    ]
    assert not Translation.objects.exists()


def test_the_access_pages_read_names_in_the_readers_language(
    client: Client, editor: Person, managers: Group
) -> None:
    name(managers, 'fa', MANAGERS_FA)
    role = Role.objects.create(code='clerk', name='Clerk')
    client.force_login(editor)

    with override_settings(LANGUAGE_CODE='fa'):
        assert MANAGERS_FA in client.get('/admin/access/bundles/').content.decode()
        bundle_page = client.get(f'/admin/access/bundles/{managers.pk}/').content.decode()

    assert MANAGERS_FA in bundle_page
    assert f'/admin/access/names/auth.group/{managers.pk}/' in bundle_page
    role_page = client.get(f'/admin/access/roles/{role.pk}/').content.decode()
    assert f'/admin/access/names/clearance_roles.role/{role.pk}/' in role_page
    assert (
        '/admin/access/names/auth.permission/'
        in client.get('/admin/access/permissions/').content.decode()
    )


def test_a_template_names_a_thing_with_or_without_the_pages_labels(managers: Group) -> None:
    name(managers, 'fa', MANAGERS_FA)
    template = Template('{% load clearance %}{{ bundle|label:labels }}|{{ bundle|label }}')

    rendered = template.render(Context({'bundle': managers, 'labels': labels_in('fa')}))

    assert rendered == f'{MANAGERS_FA}|Branch managers'


# ---------------------------------------------------------------- without the app


@pytest.fixture
def no_translations() -> Iterator[None]:
    uninstall_labels()
    yield
    install_labels(TranslatedLabels)


def test_without_the_app_a_thing_reads_as_the_code_or_its_row_says(
    no_translations: None, managers: Group
) -> None:
    Translation.objects.create(
        content_type=ContentType.objects.get_for_model(Group),
        object_pk=str(managers.pk),
        language='fa',
        name=MANAGERS_FA,
    )

    assert type(labels_in('fa')) is Labels
    assert labels_in('fa').of(managers) == 'Branch managers'
    assert labels_in('fa').description_of(managers) == ''


def test_translations_installed_without_the_core_or_before_it_are_refused() -> None:
    assert [e.id for e in order_errors(['clearance_translations'])] == ['clearance.E008']
    assert [e.id for e in order_errors(['clearance_translations', 'clearance'])] == [
        'clearance.E008'
    ]
    assert order_errors(['clearance', 'clearance_translations']) == []


def test_a_name_says_what_it_is() -> None:
    assert str(Translation(language='fa', name='x')) == 'fa: x'
