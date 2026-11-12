"""
The safety rules hold whichever way a change is made.

If these fail, somebody managing access widens what others hold without
holding it themselves - by changing the rows a rule scope reaches, giving back
a permission that was taken away, or lifting a ceiling with a second role -
and Django's own user pages hand over a superuser's account, or a role.

Each of these is a finding of the 0.1.0 review. One not yet fixed is marked
``xfail`` - strictly, so the mark is taken off by whoever fixes it.
"""

from datetime import datetime
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory, override_settings

from clearance.admin.options import protected_admin
from clearance.checks import backend_errors
from clearance.roles.models import Role, RoleBundle, RoleCeiling
from clearance.roles.services import RoleService
from clearance.safety import AccessRefused
from clearance.services import AccessService
from tests.conftest import MakeBundle, MakeUser, permission
from tests.project.accounts.models import Person
from tests.project.lending.models import Loan

pytestmark = pytest.mark.django_db

MANAGE = ('clearance.permission_view', 'clearance.permission_edit')
ATTRIBUTE = {
    'ROLE_RESOLVER': 'clearance.roles.resolvers.AttributeResolver',
    'ROLE_ATTRIBUTE': 'region',
}


def fresh(person: Person) -> Person:
    return Person.objects.get(pk=person.pk)


def staff(person: Person) -> Person:
    Person.objects.filter(pk=person.pk).update(is_staff=True)
    return fresh(person)


def admin_of(person: Person) -> Client:
    client = Client()
    client.force_login(person)
    return client


def posted(form: Any) -> dict[str, Any]:
    """What a browser would send back for ``form``, unchanged."""
    data = {}

    for name, field in form.fields.items():
        value = form[name].value()
        if field.disabled or value is None or value is False:
            continue
        if isinstance(value, datetime):  # the admin site splits it into a date and a time
            data[form.add_prefix(f'{name}_0')] = value.date().isoformat()
            data[form.add_prefix(f'{name}_1')] = value.time().isoformat()
            continue
        data[form.add_prefix(name)] = 'on' if value is True else value

    return data


# ---------------------------------------------------------------------- AccessService


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_the_rows_of_a_rule_scope_are_widened_only_by_somebody_holding_every_row(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    """Otherwise a manager holding no loan permission gives a colleague every loan."""
    rule = AccessService(actor=None).create_scope_rule(
        Loan,
        'north',
        'The north',
        [{'field': 'region', 'operator': 'is', 'value': {'constant': 'north'}}],
    )
    officers = make_bundle({'lending.loan_edit': 'north', 'lending.loan_view': 'north'})
    officer = make_user(bundles=(officers,))
    Loan.objects.create(applicant=make_user(), amount=1, region='south')
    manager = make_user(*MANAGE)  # holds nothing about loans

    with pytest.raises(AccessRefused):
        AccessService(actor=manager).change_scope_rule(
            rule, conditions=[{'field': 'amount', 'operator': 'at_least', 'value': {'constant': 0}}]
        )

    assert not Loan.objects.visible_to(fresh(officer), 'edit').filter(region='south').exists()


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_permission_taken_away_is_given_back_only_by_somebody_holding_it(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    officers = make_bundle({'lending.loan_approve': 'all'})
    officer = make_user(bundles=(officers,))
    AccessService(actor=None).revoke(officer, 'lending.loan_approve', reason='Under review')
    manager = make_user(*MANAGE)  # may not approve a loan

    with pytest.raises(AccessRefused):
        AccessService(actor=manager).restore(fresh(officer), 'lending.loan_approve')

    assert not fresh(officer).has_perm('lending.loan_approve')


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_status_action_writes_from_more_values_only_by_somebody_holding_it(
    make_user: MakeUser,
) -> None:
    action = AccessService(actor=None).create_status_action(
        Loan, 'settle', 'Settle', 'approved', [True], [False]
    )
    manager = make_user(*MANAGE)  # may not settle a loan

    with pytest.raises(AccessRefused):
        AccessService(actor=manager).change_status_action(action, start=[])


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_bundle_a_person_starts_with_is_one_they_hold(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    bundle = make_bundle(
        {
            'lending.loan_view': 'own',
            'lending.loan_edit': 'all',
            'clearance.permission_view': None,
            'clearance.permission_edit': None,
        }
    )
    role = Role.objects.create(code='officer', name='Officer', limited=False)
    RoleBundle.objects.create(role=role, group=bundle)
    officer = make_user()
    RoleService(actor=None).assign(officer, role)
    officer = fresh(officer)
    assert officer.has_perm('clearance.permission_edit')

    with pytest.raises(AccessRefused):  # their own access: loan_edit narrowed, by themselves
        AccessService(actor=officer).change_bundle(
            bundle,
            grants={
                'lending.loan_view': 'own',
                'lending.loan_edit': 'own',
                'clearance.permission_view': None,
                'clearance.permission_edit': None,
            },
        )


# ---------------------------------------------------------------------- RoleService


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_second_role_does_not_lift_a_ceiling_without_role_ceiling_edit(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    clerk_role = Role.objects.create(code='clerk', name='Clerk', limited=True)
    RoleCeiling.objects.create(role=clerk_role, permission=permission('lending.loan_view'))
    free = Role.objects.create(code='guest', name='Guest', limited=False)
    clerk = make_user(
        bundles=(make_bundle({'lending.loan_view': 'all', 'lending.loan_edit': 'all'}),)
    )
    RoleService(actor=None).assign(clerk, clerk_role)
    assert not fresh(clerk).has_perm('lending.loan_edit')  # the ceiling stops it
    manager = make_user(*MANAGE)  # without clearance.role_ceiling_edit

    with pytest.raises(AccessRefused):
        RoleService(actor=manager).assign(fresh(clerk), free)

    assert not fresh(clerk).has_perm('lending.loan_edit')


# ---------------------------------------------------------------------- Django's user pages


def test_only_the_superuser_changes_a_superusers_password(make_user: MakeUser) -> None:
    owner = make_user(superuser=True)
    owner.set_password('the-owners-own')
    owner.save()
    clerk = staff(make_user(('accounts.view_person', 'all'), ('accounts.change_person', 'all')))

    admin_of(clerk).post(
        f'/admin/accounts/person/{owner.pk}/password/',
        {'password1': 'chosen-by-the-clerk-1', 'password2': 'chosen-by-the-clerk-1'},
    )

    assert not fresh(owner).check_password('chosen-by-the-clerk-1')


def user_page(actor: Person, person: Person, change: dict[str, Any] | None = None) -> Any:
    """
    The change page of ``person`` for ``actor`` - on a plain ``ModelAdmin`` of
    the user model, guarded by the library as the site guards every one. (The
    project's own ``UserAdmin`` page cannot be opened at all in 0.1.0: see
    ``test_the_pages_answer_rather_than_fail``.)
    """
    model_admin = protected_admin(admin.ModelAdmin)(Person, admin.site)
    url = f'/admin/accounts/person/{person.pk}/change/'
    request = RequestFactory().get(url)
    request.user = actor
    page = model_admin.change_view(request, str(person.pk))

    if change is None:
        return page

    data = {**posted(page.context_data['adminform'].form), **change}
    request = RequestFactory().post(url, {k: v for k, v in data.items() if v is not None})
    request.user = actor
    request._dont_enforce_csrf_checks = True  # type: ignore[attr-defined]
    request.session = {}  # type: ignore[assignment]
    request._messages = FallbackStorage(request)  # type: ignore[attr-defined]
    return model_admin.change_view(request, str(person.pk))


@override_settings(CLEARANCE=ATTRIBUTE)
def test_nobody_gives_themselves_a_role_on_the_user_page(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    role = Role.objects.create(code='north', name='Managers of the north', limited=False)
    RoleBundle.objects.create(role=role, group=make_bundle({'lending.loan_approve': 'all'}))
    clerk = staff(make_user(('accounts.view_person', 'all'), ('accounts.change_person', 'all')))

    user_page(clerk, clerk, {'region': 'north'})

    assert not fresh(clerk).has_perm('lending.loan_approve')


def test_the_user_page_does_not_leave_nobody_able_to_manage_access(make_user: MakeUser) -> None:
    manager = make_user(*MANAGE)
    clerk = staff(
        make_user(
            ('accounts.view_person', 'all'),
            ('accounts.change_person', 'all'),
            ('accounts.delete_person', 'all'),
        )
    )
    client = admin_of(clerk)
    page = client.get(f'/admin/accounts/person/{manager.pk}/change/')
    data = posted(page.context['adminform'].form)
    data.pop('is_active')

    switched_off = client.post(f'/admin/accounts/person/{manager.pk}/change/', data)
    deleted = client.post(f'/admin/accounts/person/{manager.pk}/delete/', {'post': 'yes'})
    client.post(
        '/admin/accounts/person/',
        {'action': 'delete_selected', '_selected_action': [manager.pk], 'post': 'yes'},
    )

    assert switched_off.status_code == deleted.status_code == 403
    assert fresh(manager).is_active


def test_a_superusers_account_is_the_superusers_alone(make_user: MakeUser) -> None:
    owner = make_user(superuser=True)
    clerk = staff(
        make_user(
            ('accounts.view_person', 'all'),
            ('accounts.change_person', 'all'),
            ('accounts.delete_person', 'all'),
        )
    )
    client = admin_of(clerk)

    client.post(f'/admin/accounts/person/{owner.pk}/delete/', {'post': 'yes'})
    client.post(
        '/admin/accounts/person/',
        {'action': 'delete_selected', '_selected_action': [owner.pk], 'post': 'yes'},
    )

    assert client.get(f'/admin/accounts/person/{owner.pk}/password/').status_code == 403
    assert Person.objects.filter(pk=owner.pk).exists()
    # ... and theirs still: the superuser changes their own, and another's.
    assert (
        admin_of(staff(owner)).get(f'/admin/accounts/person/{owner.pk}/password/').status_code
        == 200
    )


@override_settings(CLEARANCE=ATTRIBUTE)
def test_the_superuser_gives_a_role_on_the_user_page(make_user: MakeUser) -> None:
    Role.objects.create(code='north', name='Managers of the north', limited=False)
    owner, person = staff(make_user(superuser=True)), make_user()

    user_page(owner, person, {'region': 'north'})

    assert fresh(person).region == 'north'


# ---------------------------------------------------------------------- the backend


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_a_backend_built_on_model_backend_is_refused_beside_the_librarys() -> None:
    """E007 names ``ModelBackend`` only; its subclasses hand back every revocation the same."""
    backends = [
        'django.contrib.auth.backends.AllowAllUsersModelBackend',
        'clearance.backends.ClearanceBackend',
    ]

    assert [error.id for error in backend_errors(backends)] == ['clearance.E007']


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
@override_settings(
    AUTHENTICATION_BACKENDS=[
        'django.contrib.auth.backends.AllowAllUsersModelBackend',
        'clearance.backends.ClearanceBackend',
    ]
)
def test_a_backend_built_on_model_backend_hands_back_what_was_taken_away(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    """Why the check above matters - it passes at start-up, and this is what follows."""
    officer = make_user(bundles=(make_bundle({'lending.loan_approve': 'all'}),))
    AccessService(actor=None).revoke(officer, 'lending.loan_approve')

    assert not fresh(officer).has_perm('lending.loan_approve')


@pytest.mark.xfail(reason='A finding of the 0.1.0 review, fixed in a later stage.')
def test_with_perm_leaves_out_whoever_a_permission_was_taken_from(
    make_user: MakeUser, make_bundle: MakeBundle
) -> None:
    officer = make_user(bundles=(make_bundle({'lending.loan_approve': 'all'}),))
    AccessService(actor=None).revoke(officer, 'lending.loan_approve')

    assert officer not in Person.objects.with_perm('lending.loan_approve')
