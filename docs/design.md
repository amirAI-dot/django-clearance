# django-clearance - design

> **Status: proposal for review (stage 0).** Nothing described here is
> implemented yet. Each section ends in something a later stage builds and
> tests; anything that changes on review is changed here first.
>
> Persian: [`design.fa.md`](design.fa.md).

**django-clearance** - role, policy and row-level access control for Django.
Denied by default.

It answers the three questions every access decision is made of, each in one
place, on top of Django's own permission tables:

| question | answered by | lives in |
|---|---|---|
| **What may this person do?** | a *policy*, asked with the object in hand | `clearance.policies` |
| **Which rows may they reach?** | the *queryset*, scoped per role | `clearance.querysets` |
| **Where does what they hold come from?** | their *roles*, the groups linked to them, and what was taken away from them alone | `clearance.roles` |

Keeping the three apart is the point. A permission class answers the first
question and nothing else: DRF calls `has_object_permission` only after a view
has resolved one object, so a list endpoint guarded by a permission class
returns every row in the table - and nothing fails, which is what makes it
dangerous. Row visibility therefore belongs to the queryset, and the viewset
base applies it itself so no endpoint can forget to.

---

## 1. Principles

1. **Denied by default.** Every gap in configuration produces a refusal or an
   empty list, never a leak:
   * an anonymous or inactive user holds nothing and sees no rows;
   * a view action no policy maps is refused - at the action level and at the
     object level;
   * a role with no scope hook on a queryset sees no rows of it;
   * a role the project never declared counts for nothing;
   * a user with no role sees no scoped rows.
2. **Misconfiguration is loud.** What can be checked at start-up is a Django
   system check (`manage.py check`, and every `runserver`), so it fails in
   development and in CI rather than as a 403 a user reports - or worse, as a
   200 nobody reports. What can only be checked against the database (a
   codename that does not exist) fails the management command that meets it.
   See section 9.
3. **Django's permission tables are the storage.** Permissions are ordinary
   `auth_permission` rows created by `migrate`; groups are `auth.Group`. So
   `user.has_perm()`, `PermissionRequiredMixin`, `{{ perms }}` in templates and
   the admin site keep working, and nothing has to be synchronised.
4. **Asking is cheap.** Working out what a person holds costs the queries
   Django's own backend already makes, whatever roles, groups and revocations
   are involved. Scoping a queryset adds a `WHERE`, never a query per row.
   Both are held by tests that count queries.
5. **Layers are opt-in.** The core has no models and no migrations; DRF is an
   optional extra; the roles app is a separate Django app. A project takes
   what it needs.
6. **No opinion about the rest.** Response envelopes, exception formats, audit
   storage and the project's user model are the project's. The library
   publishes signals and raises Django's and DRF's own exceptions.

---

## 2. Features (0.1)

What the README will list.

* **Permissions declared on the model.** `build_permissions('loan', 'loans',
  actions=(...))` in `Meta.permissions`; `migrate` creates the rows. No sync
  command.
* **Policies with object-level hooks.** `can_view(user, obj)` receives the
  object, so holding `loan_view` can mean "the loans that are yours".
  Overriding a hook keeps the codename requirement by calling `super()`.
* **Custom actions must be declared.** An `@action` that no policy lists in
  `custom_actions` is refused, and `manage.py check` names it before anybody
  calls it.
* **Row scoping per role.** `Model.objects.visible_to(user)` dispatches to
  `scope_for_<role>` hooks. Unwritten hooks return nothing.
* **Multiple roles per user.** A person's rows are the union of their roles'
  scopes; their permissions are the union of their roles' groups.
* **Roles from anywhere.** A role field on your user model, an attribute, a
  table of assignments that ships with the library, or your own resolver.
* **Roles linked to groups.** What a role may do is the groups linked to it -
  changed in the database, reaching everybody with the role at once, with
  nothing to move when somebody's role changes.
* **Taking one permission from one person.** A revocation subtracts a
  permission their groups give them, without changing their role or making
  them a group of their own.
* **Starting permissions, once.** A table in your code gives each role its
  first group on a new database - and never again, so later changes made in
  the database stay made.
* **Works with and without DRF.** One mixin scopes Django's class-based views
  and DRF's generic views alike; the DRF permission class is generated from
  the policy.
* **The same for templates and forms.** `PolicyRequiredMixin` asks the policy
  from Django's own generic views - the action read off the view, the object
  handed to the hook - and `@policy_required` does it for a function view.
* **Usable outside views.** `policy.authorize(user, 'approve', loan)` raises
  Django's `PermissionDenied` from a service, a management command or a task.
* **Signals for every change.** Assigning a role, revoking a permission,
  seeding - so a project writes its own audit trail.
* **In the admin site.** Every permission listed with the groups and roles
  that hold it; groups made and given to roles from the group page; a
  person's roles and revocations on their own page.
* **Every permission in every language.** An administrator names a permission
  or a group in any language the project offers, from the admin site, with
  no translation file and no deployment.
* **Translated.** Every message is marked for translation; English and
  Persian ship with the package.
* **Typed.** Type hints throughout, `py.typed` shipped.

---

## 3. Package layout

```
src/clearance/
    __init__.py            empty
    apps.py                ClearanceConfig - registers the system checks
    conf.py                reading and validating the CLEARANCE setting
    permissions.py         build_permissions, DEFAULT_ACTIONS, RECORD_ACTIONS
    registry.py            PermissionRegistry, ResourcePermission, registry
    policies.py            BasePolicy, SignedInReadPolicy
    resolvers.py           RoleResolver, AttributeResolver, roles_of(), reaches_every_row()
    querysets.py           ScopedQuerySet, SignedInReadQuerySet, OwnedQuerySet
    views.py               ScopedQuerySetMixin, PolicyRequiredMixin - Django CBVs (and DRF)
    decorators.py          policy_required - function views
    labels.py              label_of() - a permission's or group's name, in the reader's language
    admin.py               the permission page, and the group page extended
    checks.py              the core system checks
    signals.py             every signal the library sends
    locale/fa/LC_MESSAGES/ the Persian catalogue

    drf/                   needs djangorestframework (pip install django-clearance[drf])
        __init__.py        empty
        permissions.py     PolicyPermission - the bridge from a view action to a policy hook
        viewsets.py        ScopedModelViewSet, ScopedReadOnlyViewSet
        checks.py          every @action mapped; every scoped viewset's queryset scoped

    roles/                 a Django app with models: INSTALLED_APPS += ['clearance.roles']
        __init__.py        empty
        apps.py            label 'clearance_roles'
        models.py          RoleAssignment, RoleGroup, PermissionRevocation, StartingPermissions
        backends.py        ClearanceBackend
        resolvers.py       AssignmentResolver
        services.py        assign_role, unassign_role, revoke_permission, restore_permission
        seeding.py         giving the starting permissions once
        admin.py           roles on the group and user pages
        migrations/
        management/commands/clearance_seed.py

    translations/          a Django app with models: INSTALLED_APPS += ['clearance.translations']
        __init__.py        empty
        apps.py            label 'clearance_translations'
        models.py          PermissionTranslation, GroupTranslation
        sources.py         the label source that reads them
        admin.py           translations on the permission and group pages
        migrations/
```

Rules for the layout:

* **`__init__.py` files stay empty.** Everything is imported from the module
  that defines it: `from clearance.policies import BasePolicy`. The version is
  read with `importlib.metadata.version('django-clearance')`.
* **The core imports nothing from `drf`, `roles` or `translations`.** Each of
  them imports the core, and plugs into it - an admin page, a label source -
  through a hook the core offers. Tested by importing the core with none of
  them installed.
* **The apps' labels are `clearance_roles` and `clearance_translations`**, so
  neither can collide with a project app of the same short name.

---

## 4. The API, by example

A small lending app: customers apply for loans, officers review the ones at
their branch, administrators read everything.

### 4.1 Settings

```python
INSTALLED_APPS += ['clearance', 'clearance.roles']

# Replaces django.contrib.auth.backends.ModelBackend - see check E006.
AUTHENTICATION_BACKENDS = ['clearance.roles.backends.ClearanceBackend']

CLEARANCE = {
    'ROLES': 'accounts.roles.Role',                       # a TextChoices, or a list of codes
    'ROLE_RESOLVER': 'clearance.roles.resolvers.AssignmentResolver',
    'EVERY_ROW_ROLES': ['admin'],
    'STARTING_PERMISSIONS': 'config.access.STARTING_PERMISSIONS',
}
```

```python
# accounts/roles.py
class Role(models.TextChoices):
    ADMIN = 'admin', _('Administrator')
    OFFICER = 'officer', _('Loan officer')
    CUSTOMER = 'customer', _('Customer')
```

### 4.2 The model declares its permissions

```python
from clearance.permissions import build_permissions

class Loan(models.Model):
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    branch = models.ForeignKey(Branch, ...)
    amount = models.DecimalField(...)

    objects = LoanQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        permissions = build_permissions(
            'loan', 'loans', actions=('view', 'create', 'edit', 'approve'),
        )
```

`default_permissions = ()` turns off Django's add/change/delete/view, which
would otherwise sit beside these as a second answer to the same question.
The labels written into `auth_permission.name` are untranslated English on
purpose: a lazy translation there is resolved at import time and bakes one
language into the migration, so `makemigrations` reports drift on models
nobody touched.

### 4.3 The queryset says which rows

```python
from django.db.models import Q
from clearance.querysets import ScopedQuerySet

class LoanQuerySet(ScopedQuerySet):
    def scope_for_customer(self, user):
        return Q(applicant=user)

    def scope_for_officer(self, user):
        return Q(branch__officers=user)
    # No scope_for_admin: 'admin' is in EVERY_ROW_ROLES, so it sees every row
    # unless this queryset says otherwise.
```

### 4.4 The policy says what may be done

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class LoanPolicy(BasePolicy):
    app_label = 'loans'
    codename = 'loan'
    custom_actions = {'approve': 'can_approve'}

    def can_approve(self, user, obj=None):
        if not self.has(user, 'approve'):
            return False
        if obj is None:
            return True
        return obj.applicant_id != user.pk

loan_access = registry.register(LoanPolicy)
```

`registry.register` refuses a second policy for the same codename, and a
`custom_actions` entry naming a hook the policy does not have.

### 4.5 The view only declares

```python
from clearance.drf.viewsets import ScopedModelViewSet

class LoanViewSet(ScopedModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer
    permission_classes = [loan_access.drf_class]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        loan = self.get_object()   # only among visible_to(user), then can_approve(user, loan)
        ...
```

A Django view with templates and forms uses the same mixin, and asks the
policy with `PolicyRequiredMixin`:

```python
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin

class LoanListView(PolicyRequiredMixin, ScopedQuerySetMixin, ListView):
    policy = loan_access.policy          # 'list', read off ListView
    queryset = Loan.objects.all()

class LoanApproveView(PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):
    policy = loan_access.policy
    policy_action = 'approve'            # can_approve(user, loan)
    queryset = Loan.objects.all()
    form_class = LoanApprovalForm
```

And a function view:

```python
from clearance.decorators import policy_required

@policy_required(loan_access.policy, 'create')
def apply(request):
    ...
```

### 4.6 Outside a view

```python
loan_access.policy.allows(user, 'approve', loan)      # -> bool
loan_access.policy.authorize(user, 'approve', loan)   # raises django's PermissionDenied
Loan.objects.visible_to(user)
```

### 4.7 Roles, groups and revocations

```python
# config/access.py - read once, on a new database
STARTING_PERMISSIONS = {
    'admin': ['loans.loan_view'],
    'officer': ['loans.loan_view', 'loans.loan_approve'],
    'customer': ['loans.loan_view', 'loans.loan_create'],
}
```

```bash
python manage.py migrate
python manage.py clearance_seed
```

```python
from clearance.roles.services import assign_role, revoke_permission

assign_role(person, 'officer', by=admin)
revoke_permission(person, 'loans.loan_approve', by=admin, reason='Under review')
person.has_perm('loans.loan_approve')   # False - the officer group still gives it to everybody else
```

### 4.8 Names in every language

```python
from django.utils.translation import gettext_lazy as _

permissions = build_permissions('loan', _('loans'), actions=(...))
```

```python
from clearance.labels import label_of

label_of(permission)                 # in the language of the request
label_of(permission, language='fa')  # in a language named
label_of(group)                      # a group's name, the same way
```

The resource name may be marked for translation: what `migrate` writes into
`auth_permission.name` is still English - read with translation switched
off - while `label_of` says it in the reader's language. An administrator's
own name for a permission or a group, typed in the admin site, comes first
(8.3).

---

## 5. Multiple roles

### 5.1 Where a person's roles come from

`clearance.resolvers.roles_of(user)` answers a `frozenset` of role codes,
asked of the configured resolver and cached on the user instance for the
rest of the request.

| resolver | reads | cost |
|---|---|---|
| `clearance.resolvers.AttributeResolver` (default) | `user.<ROLE_ATTRIBUTE>` - one code, or an iterable of codes | none |
| `clearance.roles.resolvers.AssignmentResolver` | `RoleAssignment` rows | one query, once per request; none inside the permission query (5.2) |
| your own | subclass `RoleResolver`, implement `roles_of(user)` | yours |

A resolver may also implement `roles_subquery(user)`, returning a queryset of
role codes. The backend uses it in place of `roles_of`, so the roles are
looked up inside the permission query instead of before it.

A code the resolver answers that `ROLES` does not declare counts for nothing
and is logged once as a warning.

### 5.2 What a person holds

```
held = direct grants (user_permissions)
     + permissions of every group linked to any of their roles (RoleGroup)
     + permissions of their own groups (user.groups)
     - their revocations (PermissionRevocation)      <- subtracted from groups only
```

A direct grant is not cancelled by a revocation: revoking a permission that
was granted directly removes the grant instead (`revoke_permission` does
both, as the case requires). The superuser holds every permission, as in
Django.

`ClearanceBackend` overrides the group half of `ModelBackend` and keeps its
caching, so `has_perm` costs exactly the queries `ModelBackend` costs.

### 5.3 Which rows a person sees

`visible_to(user)`:

1. anonymous or inactive -> no rows;
2. superuser -> every row;
3. otherwise, for each of their declared roles, the role's scope:
   * `scope_for_<role>(user)` when the queryset defines it;
   * else every row, when the role is in `EVERY_ROW_ROLES`;
   * else nothing;
4. the rows are the **union** of those scopes; no scopes -> no rows.

A hook returns one of:

| returned | means |
|---|---|
| `Q(...)` | these rows - the cheapest to combine |
| `Q()` (empty) | every row |
| a queryset of the same model | these rows |
| `None` or `self.none()` | nothing |

With one role, the scope is applied as it is - a returned queryset is
returned unchanged. With several, `Q`s are joined with `OR` in one `filter`,
and a returned queryset joins as `Q(pk__in=queryset.values('pk'))`, so
combining never meets the restrictions of `QuerySet.__or__`. One role seeing
every row makes the answer every row. A hook returning anything else raises
`TypeError`.

A `Q` that crosses a to-many relation can repeat a row when joined with
another; the documentation says so and shows `pk__in` as the remedy.

### 5.4 In a policy

`has_role(user, *roles)` is true when the user has **any** of them.
`reaches_every_row(user)` is the queryset's answer about one object - the
superuser, or a role in `EVERY_ROW_ROLES` - for a policy deciding whether an
object needs to be the user's own. It answers *which rows*, never *what may
be done*.

---

## 6. From a view to a policy

### 6.1 DRF

`PolicyPermission` maps a request to a hook:

| view | hook |
|---|---|
| `list` | `can_list` |
| `retrieve` | `can_view` |
| `create` | `can_create` |
| `update`, `partial_update` | `can_edit` |
| `destroy` | `can_delete` |
| a custom `@action` | `custom_actions[name]`, or **refused** |
| an `APIView` (no action) | the HTTP method: `GET`/`HEAD`/`OPTIONS` -> `can_list`, `POST` -> `can_create`, `PUT`/`PATCH` -> `can_edit`, `DELETE` -> `can_delete` |

At the object level the same table applies, with the object passed to the
hook, and a custom action that is not mapped is refused there too.

`ScopedModelViewSet` and `ScopedReadOnlyViewSet` are DRF's own viewsets with
`ScopedQuerySetMixin` applied. The read-only one is composed from the read
mixins rather than trimmed from `ModelViewSet`, so DRF does not publish write
routes it never serves.

### 6.2 Django views

`PolicyRequiredMixin` is the same bridge for Django's generic views. It names
a `policy` and, optionally, a `policy_action`; without one, the action is read
off the view, as DRF's is:

| view | hook |
|---|---|
| `ListView` | `can_list` |
| `DetailView` | `can_view` |
| `CreateView` | `can_create` |
| `UpdateView` | `can_edit` |
| `DeleteView` | `can_delete` |
| any other view, with no `policy_action` | **`ImproperlyConfigured`** - never allowed by default |

A view with an object (`DetailView`, `UpdateView`, `DeleteView`, or anything
using `SingleObjectMixin`) asks the hook with the object, when `get_object()`
resolves it - so with `ScopedQuerySetMixin` the object is found among the rows
the user may see, and only then judged. A view with no object asks with
`obj=None`, in `dispatch`, before anything runs.

A refusal is Django's own: `AccessMixin.handle_no_permission`, so somebody not
signed in is sent to the login page and somebody signed in is answered 403.

`@policy_required(policy, action)` does the action-level check for a function
view. A function view judging one object calls `policy.authorize(user,
action, obj)` once it has it.

---

## 7. Settings

All under one dictionary, `CLEARANCE`.

| key | default | meaning |
|---|---|---|
| `ROLES` | required | dotted path to a `TextChoices`, or a list of codes. Each code must be a valid Python identifier, because it names a hook. |
| `ROLE_RESOLVER` | `'clearance.resolvers.AttributeResolver'` | dotted path to a `RoleResolver` |
| `ROLE_ATTRIBUTE` | `'role'` | what `AttributeResolver` reads |
| `EVERY_ROW_ROLES` | `[]` | roles that see every row of a queryset with no hook for them |
| `STARTING_PERMISSIONS` | `None` | dotted path to `{role: [app_label.codename, ...]}`, read by `clearance_seed` |
| `ROLE_GROUP_NAME` | `'role:{role}'` | the name of the group `clearance_seed` makes for a role |

---

## 8. Models and the admin site

### 8.1 `clearance.roles`

| model | fields | constraints |
|---|---|---|
| `RoleAssignment` | `user`, `role`, `assigned_by` (nullable), `assigned_at` | unique `(user, role)`; `role` among `ROLES` |
| `RoleGroup` | `role`, `group` (`auth.Group`), `linked_at` | unique `(role, group)`; `role` among `ROLES` |
| `PermissionRevocation` | `user`, `permission` (`auth.Permission`), `revoked_by` (nullable), `reason`, `revoked_at` | unique `(user, permission)` |
| `StartingPermissions` | `given_at`, `summary` (JSON) | at most one row - its presence is "already given" |

Every foreign key to a person is `settings.AUTH_USER_MODEL`. `role` is a plain
`CharField` validated against `ROLES` in `clean()` and in the services, not a
database `choices` list - so adding a role is a settings change, not a
migration.

### 8.2 Starting permissions, once

`clearance_seed`, run after every `migrate`:

1. makes sure every declared permission has its row;
2. on a database with no `StartingPermissions` row and no `RoleGroup` row,
   makes one group per role from `STARTING_PERMISSIONS`, links it, and writes
   the `StartingPermissions` row - **once**: from then on the groups are the
   database's, and no later run changes them, even for a role somebody left
   with no group;
3. lists the permissions nobody holds - what a new release added - for
   somebody to decide who gets them.

A codename in the table that does not exist fails the command and names it:
a silently skipped permission is a role that cannot do its job, found by a
person being refused rather than by a deployment failing.

### 8.3 `clearance.translations`

An administrator names permissions and groups in any language, from the
admin site. The names are rows, not translation files, because the person
typing them is not a developer and adding a language is not a deployment.

| model | fields | constraints |
|---|---|---|
| `PermissionTranslation` | `permission` (`auth.Permission`), `language`, `name`, `description` | unique `(permission, language)`; `language` among `LANGUAGES` |
| `GroupTranslation` | `group` (`auth.Group`), `language`, `name`, `description` | unique `(group, language)`; `language` among `LANGUAGES` |

The languages are the project's own `LANGUAGES` setting; offering a new one
is a settings change, not a migration.

`label_of` asks a chain of **label sources**, in order, and the first with an
answer wins:

1. the administrator's name in the reader's language - `clearance.translations`,
   when installed;
2. the developer's name, marked for translation in the code and translated in
   the project's catalogue;
3. the name stored in `auth_permission` or `auth_group`.

A source is a class with one method; the translations app adds its own to the
front of the chain when it loads, and a project can add one too. The
language is matched exactly, then by its base (`fa-ir`, then `fa`). Labelling
a page of permissions costs one query for all of them, never one per row.

The stored `name` is left alone: `migrate` writes it, and a name an
administrator typed there would be written over by the next `migrate`.

### 8.4 The admin site

Each app adds its part to the pages, through hooks in the core's admin; none
needs another installed.

| page | from | shows |
|---|---|---|
| **Permissions** (new) | `clearance` | every permission, read only - the app, the codename, its name in the reader's language, the groups holding it - searchable, and filtered by app and group. Permissions come from the code, so the page adds and deletes none. |
| + roles | `clearance.roles` | which roles hold each permission, and a filter by role |
| + translations | `clearance.translations` | its name and description in each language, editable |
| **Groups** (Django's, extended) | `clearance` | a group made with the permissions it holds, chosen two columns side by side |
| + roles | `clearance.roles` | the roles the group is given to (`RoleGroup`) |
| + translations | `clearance.translations` | its name and description in each language |
| **The user page** (the project's own) | `clearance.roles` | the person's roles, and the permissions taken away from them with why |
| **Role assignments**, **Revocations** | `clearance.roles` | each as a list of its own, for finding who holds a role or lost a permission |

The user page is the project's: the roles app adds its two sections to
whichever admin the project registered for its user model, rather than
replacing it.

Until 0.2 the pages write directly. When the safety rules come (section 15),
every form goes through the same service as everything else, so the admin
site never becomes the way round them.

---

## 9. System checks

| id | when |
|---|---|
| `clearance.E001` | `ROLES` is missing, cannot be imported, or holds a code that is not a valid identifier |
| `clearance.E002` | a `ScopedQuerySet` defines `scope_for_<x>` for a role `ROLES` does not declare - a typo that would silently deny |
| `clearance.E003` | a viewset guarded by a `PolicyPermission` has an `@action` its policy does not map |
| `clearance.E004` | a viewset using `ScopedQuerySetMixin` declares a queryset that is not a `ScopedQuerySet` |
| `clearance.E005` | `EVERY_ROW_ROLES` or `STARTING_PERMISSIONS` names a role `ROLES` does not declare |
| `clearance.E006` | `clearance.roles` is installed and `ClearanceBackend` is not in `AUTHENTICATION_BACKENDS` - revocations and role groups would do nothing |
| `clearance.E007` | `ModelBackend` is in `AUTHENTICATION_BACKENDS` beside `ClearanceBackend` - Django grants a permission when *any* backend does, so it would hand back every revoked permission |
| `clearance.E008` | `clearance.roles` or `clearance.translations` is installed without `'clearance'`, or before it - they plug into the core's admin pages and label chain, which must load first |
| `clearance.E009` | a `PolicyRequiredMixin` view has no `policy`, or no `policy_action` where none can be read off the view |

E004 is also raised at request time (`ImproperlyConfigured`), for a viewset
the URL configuration does not reach and the check therefore cannot see.

---

## 10. Signals

`clearance.signals`, each sent after the transaction commits:

| signal | sent with |
|---|---|
| `role_assigned` | `user`, `role`, `by` |
| `role_unassigned` | `user`, `role`, `by` |
| `permission_revoked` | `user`, `permission`, `by`, `reason` |
| `permission_restored` | `user`, `permission`, `by` |
| `starting_permissions_given` | `summary` - `{role: count}` |

---

## 11. What comes from DayarDarman

| | DayarDarman | django-clearance |
|---|---|---|
| `build_permissions`, `DEFAULT_ACTIONS`, `RECORD_ACTIONS` | `apps/core/permissions/registry.py` | as it is |
| `PermissionRegistry`, `ResourcePermission` | same file | as it is, plus validation of `custom_actions` |
| `BasePolicy` | `apps/core/permissions/policies.py` | `_has` becomes the public `has`; `allows` and `authorize` added; `has_role` means any of several |
| `PolicyPermission` | `apps/core/permissions/drf.py` | as it is |
| `ScopedQuerySet.visible_to` | a fixed dictionary of six medical roles | `scope_for_<role>` looked up by name for any declared role; union across roles; `Q` or queryset |
| `reaches_every_row` | `Role.every_row_roles()` | `EVERY_ROW_ROLES` |
| `Role` | a `TextChoices` in `apps/core/enums.py` | the project's own, named in `ROLES` |
| `User.role` | one column | any resolver; `RoleAssignment` for several roles |
| `RoleAccessGroup` | `role` -> `AccessGroup` (with translated names) | `RoleGroup`: `role` -> `auth.Group` |
| `AccessGroupTranslation` | a group's name per language | `GroupTranslation`, and `PermissionTranslation` beside it |
| `RevocableModelBackend` | role groups + own groups - revocations | `ClearanceBackend`, the same rule over several roles |
| `seed_roles`, `ROLE_PERMISSIONS` | "once" recorded as an audit row | `clearance_seed`, "once" recorded as a `StartingPermissions` row |
| viewset bases | with the response envelope and pagination | the scoping mixin only |
| audit rows | `AuditService` | signals |
| the medical scopes, `ROLE_PERMISSIONS` content | the project | stay in the project |

---

## 12. Compatibility

| | supported | tested in CI |
|---|---|---|
| Python | 3.11 - 3.14 | every one |
| Django | 5.2 LTS, 6.0, 6.1 | each with every Python it supports |
| Django REST framework | 3.16 and later, optional | the latest, on every Django |
| Database | any Django supports | PostgreSQL and SQLite |

A Django release is supported from its `.0` and dropped when Django drops it.

---

## 13. Conventions for this repository

* **English only in the code** - source, comments, docstrings, tests. Every
  message a person reads is marked with `gettext`; the Persian lives in
  `src/clearance/locale/fa/LC_MESSAGES/`, compiled and committed. Code review
  holds the rule; no tool checks it.
* **Documentation in English and in Persian.** Each document is written in
  English and translated beside it - `design.md` and `design.fa.md`,
  `README.md` and `README.fa.md` - and a change to one is made to the other in
  the same pull request. Code in a Persian document stays exactly as in the
  English one.
* **Every module's docstring says why it exists**, and every rule says what
  would go wrong without it.
* **Tests are named after the behaviour they hold** -
  `test_an_unmapped_action_is_refused.py`, not `test_drf.py`.
* **What is claimed about cost is tested** with `django_assert_num_queries`.
* **ruff** for lint and formatting; **mypy** with `django-stubs` on `src/`.
* **One stage per pull request**, reviewed and merged before the next starts.

---

## 14. Stages to 0.1

Each is one pull request.

| stage | delivers |
|---|---|
| 0 | this document |
| 1 | the skeleton: `pyproject.toml` (hatchling, `src/` layout, the `drf` extra), the test project, pytest, ruff, mypy, nox, GitHub Actions running the matrix - and no features |
| 2 | `permissions`, `registry`, `policies`, with their tests |
| 3 | `resolvers`, `querysets`, `views` (`ScopedQuerySetMixin`, `PolicyRequiredMixin`), `decorators`, the core system checks, with their tests and query counts |
| 4 | `drf`: the bridge, the viewsets and their checks |
| 5 | `roles`: models and migrations, the backend, the resolver, the services, `clearance_seed`, the signals; the admin pages - permissions, groups, the user page |
| 6 | `translations`: the models, `label_of` and its sources, the translations on the admin pages |
| 7 | documentation: the README with a five-minute start, the docs site, an example project; the Persian catalogue |
| 8 | used in iranbobco; whatever that shows fixed; `0.1.0` tagged, the repository made public, published to PyPI |

## 15. After 0.1

Planned for 0.2, the parts of DayarDarman that manage permissions rather than
check them:

* **The safety rules for changing permissions**: nobody changes their own;
  nobody grants what they do not hold; a change that leaves nobody but the
  superuser able to manage permissions is refused; a permission is given only
  to a role it does something for (`ONLY_FOR`); a role change takes away what
  does nothing in the new role.
* **Group management through one service**, with the admin site going through
  it rather than around it.
* **Describing permissions to a frontend** - each as a section, an action and
  whether it reads or writes - and the REST endpoints for a permission screen
  and for "what may I do".

---

## 16. Decisions

Made by the owner on review of this document.

1. **Every import names its module** - `from clearance.policies import
   BasePolicy`, never a flat `from clearance import BasePolicy`.
2. **The licence holder** is amir mohammad kashanchian.
3. **The oldest Python is 3.11.** 3.10 left support in October 2026, and
   Django 6 itself needs 3.12.
4. **The default resolver is `AttributeResolver` reading `user.role`**, the
   shape most projects already have. A project wanting several roles without
   a column of its own switches to `AssignmentResolver`.
5. **Django's own views get the same bridge as DRF** - `PolicyRequiredMixin`
   and `@policy_required` - so a project built on templates and forms gives
   up nothing. Built in stage 3.
6. **The admin site shows permissions and makes groups** - a permission page,
   the group page extended with roles, a person's roles and revocations on
   their page. Built in stage 5.
7. **Every permission and group can be named in any language** by an
   administrator, from the admin site - `clearance.translations`, in 0.1 rather
   than 0.2. Built in stage 6.
