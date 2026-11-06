# django-clearance - design

> **Status: second edition, accepted.** The first edition put roles at the
> centre. On review the owner set the order the other way round: **access
> bundles first, then row scopes and protected fields, and roles last, as an
> optional limit.** Stages 0 to 3 were built on the first edition; what this
> edition changes in them is listed in section 19.
>
> Persian: [`design.fa.md`](design.fa.md).

**django-clearance** - role, policy and row-level access control for Django.
Denied by default.

## The four layers

| | layer | the question | answered by |
|---|---|---|---|
| 1 | **Access bundles** | What may this person do? | permissions, held through named **bundles** given to people - many each |
| 2 | **Row scopes** | On which rows? | a **scope** chosen for each permission in a bundle: every row, their own, their branch's |
| 3 | **Protected fields** | Which fields of a row? | a permission of its own to **view** and to **edit** each sensitive field |
| 4 | **Roles** (optional) | What may this kind of person never do? | a **ceiling** no bundle gets past, and the bundles a role **starts with** |

A project uses the first three without ever declaring a role. Roles are for
the project that has kinds of people - customers, officers - and wants a
guarantee that a customer never holds an officer's power, whatever an
administrator does by mistake.

Above the layers, a **policy** per resource is the one place every view,
service and command asks "may this person do this, to this object?". It
answers from the layers, and adds rules no permission can say - "nobody
approves their own loan".

Keeping row scopes in the queryset rather than in a permission check is not
a style: DRF calls `has_object_permission` only once a view has resolved one
object, and Django's generic views have no such hook at all. A list protected
by a permission check returns every row in the table - and nothing fails,
which is what makes it dangerous.

---

## 1. Principles

1. **Denied by default.** Every gap produces a refusal or an empty list,
   never a leak:
   * somebody signed out, or a switched-off account, holds nothing and reaches
     no rows - whatever authentication backend is installed;
   * a permission given with no scope reaches no rows, unless the model's
     developer chose a default scope for it;
   * a protected field is left out for whoever lacks its permission, and a
     value sent for it by whoever may not edit it is refused;
   * a view action no policy maps is refused;
   * a role's ceiling stops what a bundle would give.
2. **Misconfiguration is loud.** What can be checked at start-up is a Django
   system check (`manage.py check`, every `runserver`), so it fails in
   development and in CI rather than as a 403 a person reports - or a 200
   nobody reports. What can only be checked against the database fails the
   management command that meets it. See section 14.
3. **Django's own tables are the storage.** Permissions are `auth_permission`
   rows that `migrate` creates; a bundle is an `auth.Group`; a person's
   bundles are `user.groups`. So `user.has_perm()`, `PermissionRequiredMixin`,
   `{{ perms }}` and the admin site keep working, and nothing is synchronised.
4. **Asking is cheap.** What a person holds costs the queries Django's own
   backend makes; their scopes cost one query per request, read once; a list
   scoped by them is still one query. Tests count them.
5. **Every layer is optional.** `'clearance'` in `INSTALLED_APPS` holds
   layers 1 to 3, and each is used only where a project asks for it: bundles
   when it makes one - permissions can be given to people directly; row
   scopes only on a model whose manager is a `ScopedQuerySet` - every other
   model works as Django's always have; protected fields only on a model that
   lists them. DRF, roles and translations are each added only by the project
   that wants them. The one requirement is `ClearanceBackend`, without which
   revocations and scopes would silently do nothing (E006).
6. **No opinion about the rest.** Response envelopes, exception formats, audit
   storage and the user model are the project's. The library sends signals
   and raises Django's and DRF's own exceptions.

---

## 2. Features (0.1)

What the README will list.

* **Access bundles.** Name a set of permissions and give it to anybody; a
  person may hold many. No roles needed.
* **Permissions declared on the model.** `build_permissions('order',
  'orders')` in `Meta.permissions`; `migrate` creates them.
* **Row scopes, per permission.** A bundle can give `order_view` on every
  order and `order_edit` only on the person's own branch's. The developer
  names the scopes once, in the queryset; the administrator chooses one for
  each permission, in the admin site.
* **Protected fields.** `protected_fields=('price',)` makes
  `order_view_price` and `order_edit_price`. Without the first the price is
  not shown - in the API, the forms, the admin site; without the second it
  cannot be changed.
* **Taking one permission from one person**, whatever bundle gives it.
* **Policies with object-level hooks**, which respect the row scopes:
  `allows(user, 'edit', order)` is false for an order outside the person's
  edit scope.
* **Works with and without DRF.** Mixins for Django's generic views and forms,
  a decorator for function views, and the DRF permission class, viewsets and
  serializer built from the same policy.
* **In the admin site.** Every permission with who holds it; bundles made
  with a scope chosen for each permission; a person's bundles, grants and
  revocations on their page.
* **Roles, when a project has them.** A ceiling per role, written in code,
  that no bundle or grant gets past; the bundles a role starts with; several
  roles per person, kept wherever the project keeps them.
* **Every permission and bundle named in every language** an administrator
  chooses, from the admin site.
* **Signals for every change**, for the project's own audit trail.
* **Translated and typed.** English and Persian ship with the package;
  `py.typed` too.

---

## 3. The model in one picture

```
held     = direct grants + their bundles' permissions + their roles' starting bundles' permissions
         - what was taken away from them
allowed  = held, within the ceilings of their roles            (only when roles are used)

rows     = the union of the scopes of every grant of that permission that reaches them
fields   = a protected field needs <codename>_view_<field> to be read, _edit_ to be written
```

The superuser holds every permission, reaches every row and reads every
field, as in Django.

---

## 4. Package layout

```
src/clearance/
    __init__.py            empty
    apps.py                ClearanceConfig - registers the system checks
    conf.py                reading and validating the CLEARANCE setting
    protocols.py           User - the three things the library asks of a person
    permissions.py         build_permissions: actions and protected fields
    registry.py            one policy per resource
    policies.py            BasePolicy, SignedInReadPolicy
    models.py              ScopeGrant, PermissionRevocation
    backends.py            ClearanceBackend
    grants.py              what a person holds, and with which scopes - read once per request
    services.py            AccessService: bundles, grants, scopes, revocations - every change, with signals
    querysets.py           ScopedQuerySet: named scopes, visible_to(user, action)
    fields.py              readable_fields(), writable_fields()
    forms.py               ProtectedFieldsFormMixin
    views.py               ScopedQuerySetMixin, PolicyRequiredMixin, ProtectedFieldsViewMixin
    decorators.py          policy_required
    labels.py              label_of() - a permission's or bundle's name, in the reader's language
    admin.py               the permission page; the bundle page, a scope per permission; the user page
    checks.py              the system checks
    signals.py             every signal the library sends
    migrations/
    locale/fa/LC_MESSAGES/

    drf/                   pip install django-clearance[drf]
        permissions.py     PolicyPermission
        viewsets.py        ScopedModelViewSet, ScopedReadOnlyViewSet
        serializers.py     ProtectedFieldsSerializerMixin
        checks.py

    roles/                 INSTALLED_APPS += ['clearance.roles']
        apps.py            label 'clearance_roles'
        models.py          RoleAssignment, RoleBundle, StartingBundles
        resolvers.py       RoleResolver, AttributeResolver, AssignmentResolver, roles_of()
        ceilings.py        a role's ceiling, from the code
        seeding.py         the starting bundles, once
        admin.py
        management/commands/clearance_seed.py

    translations/          INSTALLED_APPS += ['clearance.translations']
        models.py          PermissionTranslation, BundleTranslation
        sources.py         the label source that reads them
        admin.py
```

Every `__init__.py` is empty, and everything is imported from the module that
defines it. The core imports nothing from `drf`, `roles` or `translations`;
each plugs in through a hook the core offers.

---

## 5. The API, by example

A shop: orders placed by customers at one of several branches, managed by
staff, some of whom may see prices.

### 5.1 Settings

```python
INSTALLED_APPS += ['clearance']

# Replaces django.contrib.auth.backends.ModelBackend - see E006 and E007.
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']
```

Nothing else is needed for layers 1 to 3: no `CLEARANCE` setting, no roles.

### 5.2 The model declares its permissions and protected fields

```python
from clearance.permissions import build_permissions

class Order(models.Model):
    customer = models.ForeignKey(Customer, ...)
    branch = models.ForeignKey(Branch, ...)
    status = models.CharField(...)
    price = models.DecimalField(...)

    objects = OrderQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        permissions = build_permissions('order', _('orders'), protected_fields=('price',))
```

`migrate` creates `order_view`, `order_create`, `order_edit`, `order_delete`,
`order_view_price` and `order_edit_price`.

### 5.3 The queryset names its scopes

```python
from clearance.querysets import ScopedQuerySet

class OrderQuerySet(ScopedQuerySet):
    default_scope = 'all'      # optional: what a grant with no scope reaches
    scopes = {
        'own': _('Their own orders'),
        'branch': _("Their branch's orders"),
    }

    def scope_own(self, user):
        return Q(customer__user=user)

    def scope_branch(self, user):
        return Q(branch__staff=user)
```

`all` - "every row" - is always offered and needs no method.

### 5.4 Bundles, in the admin site or in code

The administrator makes them on the bundle page, choosing a scope beside each
permission. The same, in code:

```python
from clearance.services import AccessService

access = AccessService(actor=request.user)

branch_managers = access.create_bundle(
    'Branch managers',
    grants={'shop.order_view': 'branch', 'shop.order_edit': 'branch'},
)
accountants = access.create_bundle(
    'Accountants',
    grants={'shop.order_view': 'all', 'shop.order_view_price': None},
)

access.give_bundle(person, branch_managers)
access.give_bundle(person, accountants)
access.revoke(person, 'shop.order_edit', reason='Under review')
```

`person` now sees every order and its price, edits nothing - it was taken
away from them - and nobody else holding "Branch managers" lost anything.

### 5.5 The policy

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class OrderPolicy(BasePolicy):
    app_label = 'shop'
    codename = 'order'

order_access = registry.register(OrderPolicy)

order_access.policy.allows(user, 'edit', order)    # order_edit, and the order within their edit scope
order_access.policy.authorize(user, 'edit', order)  # or Django's PermissionDenied
```

### 5.6 Views, forms and the API

```python
from clearance.views import PolicyRequiredMixin, ProtectedFieldsViewMixin, ScopedQuerySetMixin

class OrderListView(PolicyRequiredMixin, ScopedQuerySetMixin, ListView):
    policy = order_access.policy          # the rows: visible_to(user, 'view')
    queryset = Order.objects.all()

class OrderUpdateView(
    PolicyRequiredMixin, ScopedQuerySetMixin, ProtectedFieldsViewMixin, UpdateView
):
    policy = order_access.policy          # the rows: visible_to(user, 'edit')
    queryset = Order.objects.all()
    fields = ('status', 'price')          # price leaves the form without order_edit_price
```

```python
@policy_required(order_access.policy, 'create')
def place_order(request):
    ...
```

```python
from clearance.drf.serializers import ProtectedFieldsSerializerMixin

class OrderSerializer(ProtectedFieldsSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('id', 'status', 'price')   # price is left out without order_view_price
```

### 5.7 Outside a view

```python
Order.objects.visible_to(user, 'edit')       # the orders they may edit
readable_fields(user, Order)                 # {'id', 'customer', 'branch', 'status'}
writable_fields(user, Order)
```

### 5.8 Roles, for a project that has them

```python
INSTALLED_APPS += ['clearance', 'clearance.roles']

CLEARANCE = {
    'ROLES': 'accounts.roles.Role',
    'ROLE_CEILINGS': 'config.access.CEILINGS',
    'STARTING_BUNDLES': 'config.access.STARTING_BUNDLES',
}
```

```python
# config/access.py
CEILINGS = {
    'customer': ['shop.order_view', 'shop.order_create'],   # a customer can never hold more
}

STARTING_BUNDLES = {
    'customer': {'Customers': {'shop.order_view': 'own', 'shop.order_create': None}},
}
```

### 5.9 Names in every language

```python
from clearance.labels import label_of

label_of(permission)                 # in the language of the request
label_of(bundle, language='fa')
```

---

## 6. Layer 1: access bundles

A **bundle** is a Django `Group`: a name and the permissions it holds. A
person's bundles are `user.groups`, so a person holds many, and giving one is
what Django has always done. What the library adds:

* **a scope beside each permission in a bundle** (layer 2);
* **revocations**: one permission taken from one person, whatever bundle
  gives it, without making them a bundle of their own. A revocation subtracts
  from what bundles give; a permission granted to the person directly is not
  revoked but removed;
* **names in every language** (`clearance.translations`);
* **one service** for every change - `AccessService` - so the admin site, an
  API and a management command all change access the same way and send the
  same signals.

`ClearanceBackend` replaces `ModelBackend`. It works out what a person holds
with the queries `ModelBackend` makes, the revocations subtracted inside the
same query, and keeps Django's caching.

---

## 7. Layer 2: row scopes

### 7.1 The scopes a model offers

A model managed with a `ScopedQuerySet` offers the scopes its queryset
declares in `scopes` - a code and a label to show the administrator - each
with a `scope_<code>(user)` method. `all` is always offered and means every
row. A hook answers with:

| answer | means |
|---|---|
| `Q(...)` | these rows - the cheapest to combine |
| `Q()` | every row |
| a queryset of the same model | these rows |
| `None` or `self.none()` | nothing |

A model managed with a plain `QuerySet` has no rows to scope: its permissions
work as Django's always have.

### 7.2 A scope for each permission

`ScopeGrant` records which scope a permission is given with: in a bundle, or
to one person directly. A bundle may give `order_view` with `all` and
`order_edit` with `branch`.

A permission given with **no** scope reaches what the queryset's
`default_scope` names. A queryset that names none - the default - gives such
a grant **no rows**: the safe answer to a grant nobody finished, and
`clearance_check` lists every one. The choice between convenience and the
strictest answer is the developer's, made once for each model:

| `default_scope` | a grant with no scope reaches | the administrator |
|---|---|---|
| left out | no rows | chooses a scope for every permission of the model |
| `'all'` | every row | chooses a scope only to narrow one |
| any scope it declares | that scope's rows | chooses a scope only to change it |

A `default_scope` the queryset does not declare is E002.

### 7.3 Which rows a person reaches

`Model.objects.visible_to(user, action='view')`:

1. signed out, or switched off -> no rows; the superuser -> every row;
2. the person does not hold the action's permission - never had it, had it
   taken away, or a role's ceiling stops it -> no rows;
3. otherwise, the scopes of every grant of that permission that reaches them
   - directly, through their bundles, through their roles' starting bundles -
   are joined with OR into **one** filter; `all` makes it every row.

The person's grants are read once per request, in one query, and kept on the
user object like Django keeps their permissions. The list is then one query,
however many scopes.

### 7.4 One object

A policy's hooks respect the scopes: handed an object of a scoped model,
`can_edit(user, obj)` requires `order_edit` **and** the object within the
person's `edit` scope. A view finds its object among `visible_to(user,
action)` already, so the hook adds no query there; asked from a service, it
costs one `exists()`.

---

## 8. Layer 3: protected fields

### 8.1 Declaring them

`build_permissions(..., protected_fields=('price',))` makes, for each field,
`<codename>_view_<field>` and `<codename>_edit_<field>`. Fields not listed
are read and written with the row's own `view` and `edit`. A protected field
must be a field of the model (E012).

### 8.2 Two rules

* **Reading:** without `view_<field>`, the field is **left out** - the key is
  not in the answer, not `null` - so nothing says it exists.
* **Writing:** without `edit_<field>`, the field is not offered in a form, and
  a value sent for it to an API is **refused**, naming the field. Ignoring it
  would leave the sender believing it changed.

### 8.3 Every door

| where | how |
|---|---|
| a Django form | `ProtectedFieldsFormMixin` drops what may not be read, and shows read-only what may be read but not written |
| a Django view | `ProtectedFieldsViewMixin` builds the form that way |
| the admin site | `ProtectedFieldsAdminMixin` hides or locks, the same way |
| a DRF serializer | `ProtectedFieldsSerializerMixin` leaves out and refuses, the same way |
| a template | `{% if perms.shop.order_view_price %}` |
| code | `readable_fields(user, Order)`, `writable_fields(user, Order)` |

The library guards the doors it provides. Code that reads
`Order.objects.values('price')` for itself is the project's to guard; the
documentation says so.

In 0.1 a field's permissions are the person's, not the row's: they take no
scope (section 20).

---

## 9. Layer 4: roles (optional)

`clearance.roles` is for a project with kinds of people.

* **Which roles a person has** is read by a resolver, from wherever the
  project keeps them: `AttributeResolver` reads `user.role` (one code, or a
  list); `AssignmentResolver` reads the app's own `RoleAssignment` rows; a
  project writes its own for anything else - `is_staff`, Django groups. A
  person may have several. A role the project never declared counts for
  nothing.
* **A ceiling**, in code: `ROLE_CEILINGS` maps a role to the permissions it
  may ever hold (`'shop.*'` for an app's every permission). What a person is
  allowed is what they hold, within the union of their roles' ceilings. A
  role with no ceiling is not limited by one. The ceiling is applied in the
  backend, after everything, so neither a bundle, a direct grant nor a
  starting bundle gets past it. It is code rather than a setting in the admin
  site on purpose: it is the guarantee against an administrator's mistake, so
  an administrator cannot widen it.
* **Starting bundles**: `RoleBundle` links a role to bundles every person
  with it holds; `clearance_seed` makes them once from `STARTING_BUNDLES` on a
  new database, and never again.
* **In a policy**, `has_role(user, *roles)` answers whose job an act is -
  "only an officer approves" - which a permission cannot.

---

## 10. From a view to a policy

### 10.1 DRF

`PolicyPermission` maps `list`/`retrieve` to `can_list`/`can_view`, `create`
to `can_create`, `update`/`partial_update` to `can_edit`, `destroy` to
`can_delete`, a custom `@action` to `custom_actions[name]` - or **refuses**
it - and an `APIView` by its HTTP method. The object level uses the same
table, with the object. The scoped viewsets narrow their queryset with the
action's scope.

### 10.2 Django views

`PolicyRequiredMixin` reads the action off the view - `ListView` `list`,
`DetailView` `view`, `CreateView` `create`, `UpdateView` `edit`,
`DeleteView` `delete` - or takes `policy_action`; a view it cannot read is
`ImproperlyConfigured`, never let through. Every view first asks with no
object, in `dispatch`; a view with an object asks again with it, once
`get_object()` has found it among `visible_to(user, action)`. A refusal is
Django's own: the login page for somebody signed out, 403 otherwise.
`@policy_required(policy, action)` does the first check for a function view.

---

## 11. Settings

All under `CLEARANCE`; layers 1 to 3 need none of it. A key the library does
not know is refused (E011).

| key | default | meaning |
|---|---|---|
| `ROLES` | required by `clearance.roles` | a `TextChoices`, or a list of codes |
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AttributeResolver'` | where a person's roles are read from |
| `ROLE_ATTRIBUTE` | `'role'` | what `AttributeResolver` reads |
| `ROLE_CEILINGS` | `None` | `{role: [permission or 'app_label.*', ...]}` |
| `STARTING_BUNDLES` | `None` | `{role: {bundle name: {permission: scope}}}`, read by `clearance_seed` |

---

## 12. Models

| app | model | holds |
|---|---|---|
| `clearance` | `ScopeGrant` | `group` or `user` (exactly one), `permission`, `scope`; unique per holder and permission |
| `clearance` | `PermissionRevocation` | `user`, `permission`, `revoked_by`, `reason`, `revoked_at`; unique per person and permission |
| `clearance.roles` | `RoleAssignment` | `user`, `role`, `assigned_by`, `assigned_at` |
| `clearance.roles` | `RoleBundle` | `role`, `group` |
| `clearance.roles` | `StartingBundles` | at most one row: the starting bundles were given |
| `clearance.translations` | `PermissionTranslation`, `BundleTranslation` | a name and a description per language in `LANGUAGES` |

Every foreign key to a person is `settings.AUTH_USER_MODEL`. Roles and
languages are validated against the settings, not stored as database
choices, so adding one is not a migration.

---

## 13. The admin site

| page | shows |
|---|---|
| **Permissions** (new, read only) | every permission, its name in the reader's language, the bundles holding it and with which scope; filtered by app and bundle - and by role with `clearance.roles` |
| **Bundles** (Django's group page, extended) | a bundle made with its permissions, **a scope chosen beside each one** from those its model offers; with `clearance.roles`, the roles that start with it; with `clearance.translations`, its name in each language |
| **The user page** (the project's own) | the person's bundles, their direct grants with their scopes, what was taken away from them and why; with `clearance.roles`, their roles |
| **Model pages** | `ProtectedFieldsAdminMixin` on any `ModelAdmin` hides or locks protected fields |

Every page writes through `AccessService`, so the admin site is never a way
round the rules.

---

## 14. System checks

| id | when |
|---|---|
| `clearance.E001` | `clearance.roles` is installed and `ROLES` is missing or not valid |
| `clearance.E002` | a `ScopedQuerySet`'s `scopes` names a scope with no method, a `scope_<x>` method is not in `scopes`, or its `default_scope` is neither `all` nor a declared scope |
| `clearance.E003` | a DRF viewset guarded by a policy has an `@action` the policy does not map |
| `clearance.E004` | a scoped view's queryset is not a `ScopedQuerySet` |
| `clearance.E005` | `ROLE_CEILINGS` or `STARTING_BUNDLES` names a role nobody declared |
| `clearance.E006` | `ClearanceBackend` is not in `AUTHENTICATION_BACKENDS` - scopes, revocations and ceilings would do nothing |
| `clearance.E007` | `ModelBackend` is beside `ClearanceBackend` - Django grants a permission when *any* backend does, so it would hand back every revocation |
| `clearance.E008` | `clearance.roles` or `clearance.translations` is installed without `'clearance'`, or before it |
| `clearance.E009` | a `PolicyRequiredMixin` view cannot ask its policy |
| `clearance.E010` | `ROLE_RESOLVER` or `ROLE_ATTRIBUTE` cannot be used |
| `clearance.E011` | `CLEARANCE` is not a dictionary, or has a key the library does not know |
| `clearance.E012` | a protected field is not a field of its model |

`clearance_check` (a command, because it reads the database) lists grants
with no scope, scopes a model no longer offers, and permissions nobody holds.

---

## 15. Signals

Each sent after the transaction commits: `bundle_created`, `bundle_changed`,
`bundle_deleted`, `bundle_given`, `bundle_taken`, `permission_granted`,
`permission_revoked`, `permission_restored`, `scope_changed`, and with
`clearance.roles`, `role_assigned`, `role_unassigned`,
`starting_bundles_given`. Each carries the person or bundle, what changed,
and `actor`.

---

## 16. What comes from DayarDarman

| DayarDarman | django-clearance |
|---|---|
| `build_permissions`, `RECORD_ACTIONS` | the same, with protected fields |
| `PermissionRegistry`, `BasePolicy`, `PolicyPermission` | the same; hooks respect row scopes |
| `ScopedQuerySet` with a hook per role | a hook per **scope**, chosen per permission in a bundle |
| `RoleAccessGroup` | `RoleBundle`: a role's starting bundles |
| `ONLY_FOR` | `ROLE_CEILINGS`, applied in the backend |
| `PermissionRevocation`, `RevocableModelBackend` | the same, in the core |
| `AccessGroupTranslation` | `BundleTranslation` |
| `AuditService` rows | signals |

---

## 17. Compatibility

| | supported | tested in CI |
|---|---|---|
| Python | 3.11 - 3.14 | every one |
| Django | 5.2 LTS, 6.0, 6.1 | each with every Python it supports |
| Django REST framework | 3.16 and later, optional | the latest |
| Database | any Django supports | PostgreSQL and SQLite |

---

## 18. Conventions for this repository

* **English only in the code**; every message marked for translation, the
  Persian in `src/clearance/locale/fa/`. Code review holds the rule.
* **Documentation in English and in Persian**, changed together; code in a
  Persian document stays exactly as in the English one.
* **Every module's docstring says why it exists**; every rule, what would go
  wrong without it.
* **Tests are named after the behaviour they hold**, and what is claimed about
  cost is counted with `django_assert_num_queries`.
* **ruff** and **mypy** (strict) on every change; one stage per pull request.

---

## 19. Stages

Stages 0 to 3 are built. This edition changes stage 3: its role-centred
scoping becomes scopes per permission, and roles move to their own stage.

| stage | delivers | |
|---|---|---|
| 0 | the design | done |
| 1 | the skeleton and CI | done |
| 2 | permissions, policies, the registry | done |
| 3 | settings, Django views, the decorator, the checks - built around roles | done; reworked in 3b |
| **3b** | layers 1 and 2: `ScopeGrant`, `PermissionRevocation`, `ClearanceBackend`, `grants`, `AccessService`, named scopes and `visible_to(user, action)`, scope-aware hooks; the role code from stage 3 moves to stage 7 | |
| 4 | layer 3: protected fields - permissions, `fields`, the form, view and admin mixins | |
| 5 | DRF: the bridge, the viewsets, the serializer mixin, their checks | |
| 6 | the admin site: the permission, bundle and user pages | |
| 7 | layer 4: `clearance.roles` - resolvers, ceilings, starting bundles, `clearance_seed` | |
| 8 | `clearance.translations` | |
| 9 | documentation, an example project, the Persian catalogue | |
| 10 | used in iranbobco; `0.1.0` tagged, made public, published | |

## 20. After 0.1

* **A grant on one row** - "Ali may edit order 42" - beside the scopes.
* **Protected fields scoped by row** - the price of their own branch's orders.
* **The safety rules for changing access**: nobody changes their own; nobody
  grants what they do not hold; a change after which nobody could manage
  access is refused.
* **REST endpoints** for a permission screen and for "what may I do".

---

## 21. Decisions

Made by the owner.

1. Every import names its module.
2. The licence holder is amir mohammad kashanchian.
3. The oldest Python is 3.11.
4. The default role resolver reads `user.role`.
5. Django's own views get the same bridge as DRF.
6. The admin site shows permissions and makes bundles.
7. Permissions and bundles can be named in any language, in 0.1.
8. **Access bundles are the core**; a project needs no roles.
9. **A row scope is chosen per permission** within a bundle.
10. **Roles limit, and may start a person with bundles** - which the ceiling
    limits too.
11. **Fields can be protected**, each with its own view and edit permission.

12. A permission given with **no scope** reaches the model's
    **`default_scope`** - and **no rows** when the developer named none.
13. In 0.1, **a field's permissions are the person's**, not scoped by row.
14. **Ceilings are written in code**, not in the admin site, so they hold
    whatever an administrator does.
15. **A protected field is left out** when it may not be read, and **a value
    sent for it is refused** when it may not be written.
16. **`'clearance'` is one app with models**, holding layers 1 to 3.
17. **Every layer is optional**, used only on the models and in the projects
    that ask for it; the one requirement is `ClearanceBackend`.
