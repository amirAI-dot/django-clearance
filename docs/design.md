# django-clearance - design

> **Status: third edition, accepted.** The second edition set the order -
> access bundles first, roles last - and the owner accepted it. This edition
> adds what makes the library work the moment it is installed, and makes the
> admin site the place an administrator does everything the library can do:
> a **default** that needs no code for any model, a **custom** way for the
> models that need more, actions an administrator makes without code, row
> scopes and protected fields made in the admin site, roles kept in the
> database, and the safety rules that stop the admin site handing anybody
> everything. Stages 0 to 3 were built on the first edition; section 22 says
> what changes in them.
>
> Persian: [`design.fa.md`](design.fa.md). How to use the library, rather
> than why it is built so: [`guide.md`](guide.md).

**django-clearance** - role, policy and row-level access control for Django.
Denied by default.

## In one paragraph

Install it, run `migrate`, open the admin site. Every model already has its
four permissions - Django makes them - and every action the code exposes has
one of its own, found on its own. The administrator makes **bundles** of
permissions and gives them to people; chooses, beside each permission, the
**rows** it reaches; marks the **fields** that need a permission of their
own; makes **actions** that change a status, without code; and, when the
project has kinds of people, makes **roles** with a **ceiling** no bundle
gets past. A developer writes code only for what no administrator can: a
scope too intricate for the rule builder, a policy rule no permission can
say, a behaviour that needs a view.

## The four layers

| | layer | the question | default (no code) | custom (code) |
|---|---|---|---|---|
| 1 | **Access bundles** | What may this person do? | Django's four permissions per model; actions found in the code; status actions made in the admin site | `build_permissions` for other names; a policy for rules |
| 2 | **Row scopes** | On which rows? | scopes built in the admin site from rules | `scope_<name>` methods in a `ScopedQuerySet` |
| 3 | **Protected fields** | Which fields of a row? | fields marked in the admin site | `protected_fields=(...)` in `build_permissions` |
| 4 | **Roles** (optional) | What may this kind of person never do? | roles, their ceilings and starting bundles made in the admin site | roles and ceilings seeded from code |

Default and custom are not two modes of the library: they are chosen for
**each model**, and mixed freely. A project can leave ninety models to the
default and write code for the three that need it.

Above the layers, a **policy** per resource is the one place every view,
service and command asks "may this person do this, to this object?". A model
with no policy of its own is asked through a default one, built from its
permissions.

Row scopes live in the queryset rather than in a permission check: DRF calls
`has_object_permission` only once a view has resolved one object, and
Django's generic views have no such hook at all. A list protected by a
permission check returns every row - and nothing fails, which is what makes
it dangerous.

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
   * an action - found in the code or made in the admin site - is held by
     nobody until somebody is given it;
   * a role's ceiling stops what a bundle would give.
2. **It works the moment it is installed.** `migrate` makes every model's
   permissions and every action's; the admin site manages them. Code is for
   what an administrator cannot express, never for wiring.
3. **No permission that does nothing.** Every permission in the admin site
   is checked somewhere: Django's four by the views and the admin site, a
   found action by the code it was found in, a status action by the doors a
   value is written through. An administrator cannot type a permission
   nothing checks - it would look like control and be none.
4. **Misconfiguration is loud.** What can be checked at start-up is a Django
   system check; what only the database can say fails `clearance_check`.
5. **Django's own tables are the storage.** Permissions are `auth_permission`
   rows; a bundle is an `auth.Group`; a person's bundles are `user.groups`.
   `user.has_perm()`, `{{ perms }}` and Django's admin keep working.
6. **Asking is cheap.** What a person holds costs the queries Django's own
   backend makes; their scopes, one query per request, read once; a scoped
   list, one query. Tests count them.
7. **Every layer is optional**, used only on the models and in the projects
   that ask for it. The one requirement is `ClearanceBackend`, without which
   revocations and scopes would silently do nothing.
8. **The admin site is never the way round the rules.** Every page writes
   through the one service the code uses, under the same safety rules.
9. **Code, the admin site, or both.** Everything an administrator does in the
   admin site, a developer can write in code; and the admin site is optional -
   without `django.contrib.admin` the library works whole. What code
   declares, the admin site shows read only.

---

## 2. Features (0.1)

What the README will list.

* **Works on install.** Every model's view, create, edit and delete
  permissions, made by `migrate` - and those of every model added later.
* **Access bundles.** Name a set of permissions and give it to anybody; a
  person may hold many. No roles needed.
* **Row scopes, per permission**, built in the admin site from simple rules -
  "the branch is the person's branch" - or written in code when a rule cannot
  say it.
* **Protected fields**, marked in the admin site or in code: the price of an
  order is not shown, or not changed, without its own permission - in the
  API, the forms and the admin site.
* **Actions without code.** "Approve an order" made in the admin site as
  "may set the status to approved or rejected", and enforced wherever the
  status is written.
* **Actions found in the code.** Every DRF `@action`, every admin action and
  every view that names an action gets its permission on `migrate`, with no
  permission code written.
* **Roles, when a project has them**, made in the admin site: a ceiling per
  role that no bundle gets past, and the bundles a role starts with.
* **Safety rules.** Nobody changes their own access; nobody gives what they do
  not hold; nobody leaves the platform with nobody able to manage access.
* **A complete admin site**, right-to-left in Persian and dark-mode aware:
  bundles as a grid of models and actions with a scope beside each, a rule
  builder, protected fields, actions, roles and ceilings, each person's whole
  standing.
* **Every kind of view.** DRF's `APIView`, generic views, mixins, viewsets,
  `ModelViewSet` and `@api_view`; Django's generic views and function views.
* **Access as code.** Bundles, roles and ceilings written in a file kept in
  git and applied by `clearance_sync`, which shows every change first with
  `--dry-run` and fails CI with `--check` when the database differs. What the
  file declares is read only in the admin site.
* **The admin site is optional.** Everything works without it.
* **Taking one permission from one person**, whatever bundle gives it.
* **Policies** with object-level hooks that respect the row scopes.
* **Every permission, bundle and role named in every language.**
* **Signals for every change**, for the project's own audit trail.
* **Translated and typed.**

---

## 3. The model in one picture

```
held     = direct grants + their bundles' permissions + their roles' starting bundles' permissions
         - what was taken away from them
allowed  = held, within the ceilings of their roles            (only when roles are used)

rows     = the union of the scopes of every grant of that permission that reaches them
fields   = a protected field needs its view permission to be read, and its edit one too to be written
values   = a status action's values need that action's permission to be written
```

The superuser holds every permission, reaches every row, reads and writes
every field and value.

---

## 4. Package layout

```
src/clearance/
    __init__.py            empty
    apps.py                ClearanceConfig - registers the checks, finds the actions on migrate
    conf.py                reading and validating the CLEARANCE setting
    protocols.py           User - the three things the library asks of a person
    permissions.py         build_permissions; which permission an action of a model needs
    registry.py            one policy per resource, and the default policy for every other model
    policies.py            BasePolicy, ModelPolicy, SignedInReadPolicy
    models.py              ScopeGrant, PermissionRevocation, ScopeRule and its conditions,
                           ProtectedField, StatusAction and its values, Declared
    backends.py            ClearanceBackend
    grants.py              what a person holds, and with which scopes - read once per request
    limits.py              what a layer above bundles adds: starting bundles, a ceiling
    rules.py               a ScopeRule's conditions, checked and turned into a Q
    actions.py             status actions, and writable_values()
    health.py              what only the database can say is wrong - for clearance_check
    discovery.py           the actions found in the code, and their permissions on migrate
    writes.py              refused_writes() - what a person may not write, of what they sent
    services.py            AccessService: every change, under the safety rules, with signals
    safety.py              the safety rules
    declared.py            the ACCESS file: read, compared with the database, applied
    querysets.py           ScopedQuerySet: named scopes, visible_to(user, action)
    fields.py              readable_fields(), writable_fields()
    forms.py               ProtectedFieldsFormMixin
    views.py               ScopedQuerySetMixin, PolicyRequiredMixin, ProtectedFieldsViewMixin
    decorators.py          policy_required
    labels.py              label_of(), labels_in() - how a thing reads in the reader's language
    templatetags/          {{ thing|label:labels }}
    admin/                 'clearance.admin.apps.ClearanceAdminConfig', for 'django.contrib.admin'
        apps.py            ClearanceAdminConfig - the library's site as the default one
        sites.py           ClearanceAdminSite - every ModelAdmin given the hooks, the pages added
        options.py         the hooks: policies, rows, fields, values, actions
        views.py           PageSet, and the overview, bundles, people and permissions pages
        scopes.py          the row scopes pages and the rule builder
        protection.py      the protected fields pages
        actions.py         the actions pages
        standing.py        Standing, PermissionGrid
        discovery.py       AdminActionFinder
        checks.py          E016
    templates/, static/    the pages' templates, stylesheet and rule builder script - no build step
    checks.py              the system checks
    signals.py             every signal the library sends
    management/commands/   clearance_sync, clearance_check
    migrations/
    locale/fa/LC_MESSAGES/ the Persian catalogue, compiled - each optional app has its own

    drf/                   pip install django-clearance[drf]
        permissions.py     PolicyPermission, ModelPolicyPermission - writes guarded
        viewsets.py        ScopedModelViewSet, ScopedReadOnlyViewSet, ProtectedSerializerMixin
        serializers.py     ProtectedFieldsSerializerMixin
        discovery.py       APIViewFinder - @actions and policy_action
        checks.py          E003, E009

    roles/                 INSTALLED_APPS += ['clearance.roles']
        models.py          Role, RoleAssignment, RoleBundle, RoleCeiling
        resolvers.py       RoleResolver, AssignmentResolver, AttributeResolver, roles_of(), has_role()
        limits.py          RoleLimits - installed in clearance.limits when the app starts
        services.py        RoleService
        pages.py, admin.py the roles pages, mounted beside the access pages
        checks.py          E008, E010
        declared.py        the roles section of the ACCESS file
        signals.py
        locale/fa/LC_MESSAGES/

    translations/          INSTALLED_APPS += ['clearance.translations']
        models.py          Translation - a name and a description per language, of anything named
        labels.py          TranslatedLabels - installed in clearance.labels when the app starts
        services.py        TranslationService
        pages.py, admin.py the names page, linked from each bundle, role and permission
        checks.py          E008
        signals.py
        locale/fa/LC_MESSAGES/
```

Every `__init__.py` is empty; everything is imported from the module that
defines it. The core imports nothing from `drf`, `roles` or `translations`.

---

## 5. The API, by example

A shop: orders placed by customers at one of several branches, managed by
staff, some of whom may see prices.

### 5.1 The default: no code

```python
INSTALLED_APPS += ['clearance']

# Replaces django.contrib.auth.backends.ModelBackend - see E006 and E007.
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

# Every DRF view asks the model's policy, unless it names another.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

```python
class Order(models.Model):          # nothing about access in the model
    customer = models.ForeignKey(Customer, ...)
    branch = models.ForeignKey(Branch, ...)
    status = models.CharField(choices=Status.choices, ...)
    price = models.DecimalField(...)
```

`migrate` has made `shop.view_order`, `add_order`, `change_order` and
`delete_order`, as Django always has. In the admin site the administrator:

1. makes a **row scope** for orders, "Their branch": *branch* - *is* - *the
   person's branch*;
2. marks **price** as protected;
3. makes a **status action**, "Approve": *status* to *approved* or
   *rejected*, from *pending*;
4. makes a **bundle**, "Branch managers": view and edit orders in "Their
   branch", and "Approve" in "Their branch" - but not the price;
5. gives the bundle to people.

Every list of orders now shows a branch manager their branch's orders, with
no price, and lets them approve one - in the API, in Django's views, and in
the admin site.

### 5.2 Custom: code for what the admin site cannot say

```python
from clearance.permissions import build_permissions
from clearance.querysets import ScopedQuerySet

class OrderQuerySet(ScopedQuerySet):
    default_scope = 'all'      # optional: what a grant with no scope reaches
    scopes = {
        'own': _('Their own orders'),
        'paid_this_month': _("This month's paid orders"),
    }

    def scope_own(self, user):
        return Q(customer__user=user)

    def scope_paid_this_month(self, user):
        return Q(payments__status='paid', payments__paid_at__gte=month_start())

class Order(models.Model):
    ...
    objects = OrderQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        permissions = build_permissions('order', _('orders'), protected_fields=('price',))
```

Code scopes and admin-built ones are offered side by side; code-declared
protected fields and admin-marked ones are enforced the same way.

### 5.3 A policy, for a rule no permission can say

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class OrderPolicy(BasePolicy):
    app_label = 'shop'
    codename = 'order'

    def can_edit(self, user, obj=None):
        if not super().can_edit(user, obj):
            return False
        return obj is None or obj.status != 'delivered'   # nobody edits a delivered order

order_access = registry.register(OrderPolicy)
```

A model with no policy of its own is asked through `ModelPolicy`, which does
what `BasePolicy` does with the model's own permissions.

### 5.4 Every kind of view

| view | permission | rows |
|---|---|---|
| `APIView` | `ModelPolicyPermission`, by HTTP method | `Order.objects.visible_to(request.user, 'view')` |
| `GenericAPIView`, `generics.*` | the same | `ScopedQuerySetMixin` narrows `queryset` |
| `ViewSet` | by action | `visible_to` |
| `GenericViewSet` with mixins | by action | `ScopedQuerySetMixin` |
| `ModelViewSet` | by action | `ScopedQuerySetMixin`, or `ScopedModelViewSet` |
| `@api_view` function | `@permission_classes([...])` | `visible_to` |
| Django `ListView`, `DetailView`, `UpdateView`, ... | `PolicyRequiredMixin` | `ScopedQuerySetMixin` |
| Django function view | `@policy_required(policy, action)` | `visible_to` |

```python
class OrderListCreate(ScopedQuerySetMixin, generics.ListCreateAPIView):
    queryset = Order.objects.all()          # narrowed to visible_to(user, 'view')
    serializer_class = OrderSerializer      # price left out without its permission

class OrderReport(APIView):
    def get(self, request):
        orders = Order.objects.visible_to(request.user, 'view')
        ...
```

`ScopedModelViewSet` is a `ModelViewSet` with three things added, each of
which works on its own on any other DRF view: `ScopedQuerySetMixin`,
`ModelPolicyPermission`, and `ProtectedSerializerMixin`, which gives the
view's serializer `ProtectedFieldsSerializerMixin` whether or not it was
written to. `ScopedReadOnlyViewSet` is the same on a `ReadOnlyModelViewSet`.

### 5.5 Actions found in the code

```python
class OrderViewSet(ScopedQuerySetMixin, viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def print_invoice(self, request, pk=None):    # shop.order_print_invoice, made on migrate
        ...

class OrderPrintView(APIView):
    policy_action = 'print_invoice'                # the same permission

class OrderAdmin(admin.ModelAdmin):
    actions = ['export_excel']                     # shop.order_export_excel

@policy_required(order_access.policy, 'refund')    # shop.order_refund
def refund(request, pk):
    ...
```

### 5.6 Outside a view

```python
Order.objects.visible_to(user, 'edit')       # the orders they may edit
readable_fields(user, Order)                 # {'id', 'customer', 'branch', 'status'}
writable_values(user, Order, 'status')       # {'pending', 'cancelled'} - not approved
order_access.policy.authorize(user, 'edit', order)
```

### 5.7 In code, the same as in the admin site

```python
from clearance.services import AccessService

access = AccessService(actor=request.user)

managers = access.create_bundle(
    'Branch managers',
    grants={'shop.view_order': 'branch', 'shop.change_order': 'branch'},
)
access.give_bundle(person, managers)
access.revoke(person, 'shop.change_order', reason='Under review')
```

### 5.8 Access as code

```python
# config/access.py - CLEARANCE = {'ACCESS': 'config.access.ACCESS'}
ACCESS = {
    'bundles': {
        'Branch managers': {'shop.view_order': 'branch', 'shop.order_approve': 'branch'},
        'Accountants': {'shop.view_order': 'all', 'shop.view_order_price': None},
        'Customers': {'shop.view_order': 'own', 'shop.add_order': None},
    },
    'status_actions': {                  # for a model keeping Django's permissions
        'shop.Order': {
            'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
        },
    },
    'roles': {                           # with clearance.roles installed
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.view_order', 'shop.add_order'],   # None: no ceiling
            'bundles': ['Customers'],
        },
    },
}
```

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs from the file
python manage.py clearance_sync              # apply, and say what changed
```

**The file owns what it names, and nothing else.** A sync makes what the file
adds, changes what it changes, and deletes what it once named and names no
more. A bundle, role or status action made in the admin site is never touched
until the file comes to name it - the sync says so - and from then on the file
owns it. Who is given a bundle or a role is not the file's to say: that stays
in the admin site.

A sync is listed whole before anything is written, and applied in one
transaction through the same services the admin site uses, as the system: a
sync that would leave nobody able to manage access changes nothing. What the
file owns is refused to every person - the superuser too - because the next
sync would put it back; the admin site shows it as *declared in code*.

`bundles` and `status_actions` are the core's sections; `clearance.roles`
adds `roles` when it is installed. E001 checks at start-up what can be told
without the database - that the file reads, and says nothing that cannot be;
whether every permission and scope it names exists is `--check`'s to say.

---

## 6. Default and custom permissions

A model's permissions are its **default** ones unless it declares its own:

| | default | custom |
|---|---|---|
| declared by | Django, for every model | `build_permissions` in `Meta.permissions`, with `default_permissions = ()` |
| view / create / edit / delete | `view_order`, `add_order`, `change_order`, `delete_order` | `order_view`, `order_create`, `order_edit`, `order_delete` |
| a field | `view_order_price`, `change_order_price` | `order_view_price`, `order_edit_price` |
| an action | `order_<action>` | `order_<action>` |

`permission_for(model, action)` answers which permission an action of a model
needs, whichever it is, and every part of the library asks it - so nothing
anywhere spells a permission's name by hand. A model added later and
migrated has its permissions at once, because Django makes them.

A model that declares its own permissions turns Django's off with
`default_permissions = ()`; one that kept both would offer a permission
nothing checks, and is refused (E014). Django's own admin pages ask
`permission_for` too, so a model with custom permissions is edited in the
admin site by whoever holds them, not only by the superuser.

**`migrate` makes the locks; `clearance_sync` hands out the keys.** `migrate`
makes every permission - a model's, a field's, an action's, found in the code
or declared there - the way Django makes its own: added, never taken away,
and harmless, because nobody holds a new permission until given it. Giving
access - the bundles, roles and ceilings an `ACCESS` file declares - is
`clearance_sync`'s, an explicit step that shows what it will change before it
changes it. A project that wants one command sets `SYNC_ON_MIGRATE`: the sync
then runs once, at the end of a forward `migrate` of the default database -
after the last app has made its permissions - never while a test database is
made, and never on a migration backwards.

The library's own access to itself has its permissions too:
`clearance.permission_view`, `permission_create`, `permission_edit`,
`permission_delete`, and `clearance.role_ceiling_edit`. The superuser holds
them; nobody else does until given them.

---

## 7. Layer 1: access bundles

A **bundle** is a Django `Group`. A person's bundles are `user.groups`, so a
person holds many. The library adds: a scope beside each permission in a
bundle; revocations - one permission taken from one person, whatever bundle
gives it; names in every language; and one service, `AccessService`, through
which every page and every line of code changes access.

`ClearanceBackend` replaces `ModelBackend`. It works out what a person holds
with the queries `ModelBackend` makes, revocations and ceilings subtracted
inside the same query, and keeps Django's caching.

---

## 8. Actions

Beyond view, create, edit and delete, a model has the actions its project
gives it. There are two kinds, and an administrator cannot make a third -
a permission with nothing behind it (principle 3).

### 8.1 Status actions, made in the admin site

Most actions change a value: approving an order sets its status to
*approved*, shipping it to *shipped*, publishing a post to *published*. A
**status action** says exactly that, and needs no code:

| | |
|---|---|
| model | Order |
| name | Approve |
| field | `status` - a field with choices, or a boolean |
| to | *approved*, *rejected* |
| from | *pending* - optional |

Saving it makes `shop.order_approve`. Whoever lacks it cannot write those
values: a form offers the choice without them and refuses one sent anyway,
naming the field; the admin site does the same, and an API refuses
them, naming the field and the value. A status action is scoped
like any permission - "approve, in their branch" - and is asked of the
model's policy with the row, so a hook such as "never your own loan" holds
too. Several actions may share a field, and a value no action claims is
written with the row's own `edit`.

`from` is read off the row as it stands: a new row starts from the field's
default. The value a row holds already is always writable - keeping it is no
change.

Made in the admin site, through `AccessService`, a status action is refused
when its field has no choices and is not yes or no, when a value is not one
of the field's, or when its code is an action the model has already. Two
more refusals hold, because a change can give somebody what nobody gave them:

* **releasing a value, or deleting the action, needs the action on every
  row** - the value is then written by whoever may edit the row;
* **nobody lets an action they hold write from more values** (`own_action`),
  and nobody who does not hold it does either: it gives whoever holds it
  more. So that change is the superuser's, and the `ACCESS` file's.

The same, in code - in `build_permissions`, or in the `ACCESS` file for a
model that keeps Django's permissions - and shown read only in the admin
site:

```python
permissions = build_permissions(
    'order', _('orders'),
    status_actions={
        'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
        'ship': {'field': 'status', 'to': ['shipped']},
    },
)
```

### 8.2 Actions found in the code

An action that does something new - prints an invoice, exports a sheet,
refunds a payment - needs code, but no permission code. A policy decides an
action with no hook by its permission and its scope, as it does the standard
four, so `policy_action = 'print_invoice'` needs nothing written for it.
`migrate` (and `clearance_sync`) finds every one in the URLconf and makes its
permission:

| in the code | becomes |
|---|---|
| a DRF `@action` on a viewset asking a policy | `<codename>_<action>` |
| `policy_action = '...'` on an `APIView` or a Django view | the same |
| `@policy_required(policy, '...')` on a function view | the same |
| an entry in a `ModelAdmin`'s `actions` with no `permissions=` | the same; the admin action is offered only to whoever holds it, and runs over the rows its scope reaches |

A found action is held by nobody until it is given; a misspelled one is
therefore refused to everybody, and shows in the admin site under the name it
was misspelled with. An action a policy wrote a hook for is not found: the
hook decides it, and declares its permission with the model if it uses one -
a permission made for it would be one nothing checks. One no longer in the
code is marked as gone in the admin site, and `clearance_check` lists it.

Finding is done by `ActionFinder`s, one per kind of code, so the DRF and
admin site doors add theirs without changing anything else.

---

## 9. Layer 2: row scopes

### 9.1 The scopes a model offers

* **`all`** - every row - always.
* **Rule scopes**, built in the admin site (9.2), for any model.
* **Code scopes**, for a model managed with a `ScopedQuerySet`: `scope_<code>`
  methods listed in `scopes`, for a rule no builder can say.

A permission given with no scope reaches the queryset's `default_scope`; with
none named - the default - no rows. The choice is the developer's, once per
model. A model with a plain manager has no queryset to name one, so a grant
with no scope reaches every row, as Django always has, until a scope is
chosen for it.

### 9.2 The rule builder

A **rule scope** is a name and conditions, joined by *all of* or *any of*.
Each condition is three parts:

| part | may be |
|---|---|
| a field | a field of the model, or one reached through its relations, at most `RULE_DEPTH` (three) steps away |
| an operator | is, is not, is one of, contains, is empty, before, after, at least, at most |
| a value | a constant - "Tehran" - or the person's own: *the person*, *the person's branch*, any field of the user reached the same way |

So "Their branch" is *branch - is - the person's branch*; "Their own" is
*customer, user - is - the person*; "Large orders" is *price - at least -
10,000,000*.

A rule is checked when it is saved, against the model as it is: every field
must exist, every operator suit its field, and **no condition may read a
protected field** or the user's password - a filter on the price would tell
whoever lacks `view_price` what the price is. A constant must be a value the
field can hold, and one of its choices when it has them; a value of the
person's must hold the same kind of thing as the field. Every problem is
named, condition by condition. A rule becomes a Django `Q` - never SQL - when
a list is asked for. A rule whose field has gone since it was saved
**reaches nothing** rather than everything: it is logged, and
`clearance_check` lists it.

A rule and a code scope are offered side by side, and a person's rows are the
union of every scope that reaches them. A rule's code is a name of its own:
never `all`, never a code scope of its model.

Rules are made, changed and deleted through `AccessService`, under the
library's own permissions, and two more refusals hold:

* **nobody changes the rows of a rule their own grants are in** - it would
  widen their own access (`own_scope`); renaming it is no change to anybody's
  rows;
* **changing its rows needs every permission granted in it, on every row** -
  it gives each of them with other rows, and somebody holding nothing about
  a model could otherwise widen "the north" to everything for a colleague;
* **a rule still chosen in a grant is not deleted** - the grant would reach
  nothing without anybody deciding it should. Its grants are moved first.

### 9.3 Which rows a person reaches

`visible(queryset, user, action='view')`, for any queryset of any model -
`Model.objects.visible_to(user, action)` on a `ScopedQuerySet`:

1. signed out, or switched off -> no rows; the superuser -> every row;
2. the person does not hold the action's permission -> no rows;
3. otherwise the scopes of every grant of it that reaches them are joined
   with OR into **one** filter of the queryset asked about; `all` makes it
   every row. A scope that answers with a queryset joins as `pk__in` it, so
   whatever the queryset was narrowed by already is kept.

`visible` asks a `ScopedQuerySet` through its `visible_to`, so a queryset
that answers in a way of its own - `SignedInReadQuerySet`, or a project's -
gives a view, the admin site and a policy the answer it gives itself.

The person's grants are read once per request, in one query, and a model's
rules once per request, in one more; a list then costs its own query and
nothing else. A model with a plain manager is scoped by rule with no change
to its code: a view asks `visible`, and `ScopedQuerySetMixin` does it for any
queryset.

### 9.4 One object

Handed an object, a policy's hook requires the permission **and** the object
within the person's scope for that action. A view finds its object among
`visible_to(user, action)` already; asked from a service, it costs one
`exists()`.

### 9.5 What is written

A scope narrows what a person writes as surely as what they read. Once a row
is saved, and inside the transaction that saved it, every door asks whether
it is among the rows the person reaches for the action - `create` for a new
row, the view's own action for one changed - and a row that is not is
refused and the write undone. So somebody given `create` for "their own"
makes no row for anybody else, and nobody edits a row out of the rows they
reach, to where they could never have reached it.

It is asked after the write because a scope is a query: whether a row is "of
their branch" is the database's to say, of the row as it is saved - its
many-to-many fields included. A grant of `create` with no scope reaches the
model's `default_scope`, as any grant does - and so nothing, on a
`ScopedQuerySet` that names none.

`ScopedQuerySetMixin` asks in `form_valid`, `perform_create` and
`perform_update`; `ProtectedFieldsSerializerMixin` in `save`, so a view's own
`perform_create` is covered too; the admin site once the row and its inlines
are saved. A view that saves by hand asks with
`clearance.writes.require_within_scope(user, action, obj)`.

---

## 10. Layer 3: protected fields

### 10.1 Declaring them

* in the admin site: choose a model and a field, mark it protected;
* in code: `build_permissions(..., protected_fields=('price',))`.

Either makes the field's view and edit permissions, named the way the
model's own are: `shop.order_view_price` and `shop.order_edit_price` on a
model declaring its own, `shop.view_order_price` and `shop.change_order_price`
on one keeping Django's. The password field and the primary key cannot be
protected - the first is never shown anyway, the second is how a row is
found - and nor can a relation another model has to this one.

### 10.2 Two rules

* **Reading:** without the view permission, the field is **left out** - the
  key is not in the answer.
* **Writing:** without the edit permission, the field is not offered in a
  form, and a value sent for it to an API is **refused**, naming the field.

A field that may not be read may not be written either: a form offering it
would show what it holds. A field's permissions take no scope - they are the
person's, not the row's (decision 13) - so a grant of one with a scope is
refused.

### 10.3 Every door

| where | how |
|---|---|
| a Django form | `ProtectedFieldsFormMixin` drops what may not be read, and shows disabled what may not be written - Django then keeps the value the row holds, whatever is sent |
| a Django view | `ProtectedFieldsViewMixin` builds the form that way, and gives the template `readable_fields` and `writable_fields` |
| the admin site | every `ModelAdmin` on `ClearanceAdminSite`, with no mixin: left out of the form, the list, the search, the filters, the ordering and the date hierarchy, and refused as a filter typed into the address bar (`?price__gte=`); read only, in the form and in `list_editable`, where it may not be written |
| a DRF serializer | `ProtectedFieldsSerializerMixin` leaves out, locks and refuses - under whatever name the serializer gives the field (`source=`), and in a serializer nested in it, written out or made by `depth`; on every serializer, `ModelPolicyPermission` and `PolicyPermission` refuse what may not be written |
| a DRF view | `ProtectedSerializerMixin` - in `ScopedModelViewSet` already - has `SearchFilter` and `OrderingFilter` leave the field out; a filter of the project's own asks `path_readable` |
| a template | `{% if perms.shop.view_order_price %}` |
| code | `readable_fields(user, Order)`, `writable_fields(user, Order)` |

The library guards the doors it provides; `Order.objects.values('price')` in
the project's own code is the project's to guard, and the documentation says
so. In 0.1 a field's permissions are the person's, not the row's.

A field has the one pair of permissions however many models show it: it is
protected on a proxy of its model, and on a model that inherits it from a
parent with a table of its own, by the permissions of the model it is a
field of. A status action is claimed on a proxy the same. And a relation is
protected under its column's name too - `officer_id` is `officer`.

A field choosing a related row - in a form of the admin site, and in a
protected serializer - offers the rows of that model the person may view,
and the one the row holds already: a list of every loan on a payment's page
showed them to somebody who may see none, and an API took any loan's key,
answering whether it exists. Reference data everybody chooses from - the
branches - is read through `SignedInReadQuerySet`.

A permission is known by its app and its codename, so a field's permission
that another model of the app has already would be that one: protecting the
field is refused, and so is a status action whose permission another model
has - in the admin site, and at start-up for a field protected in code
(E012).

What is protected is read once per request, in one query over the whole
table - it holds the handful of fields a project protects - and kept on the
user beside their grants.

### 10.4 Protecting and unprotecting

`AccessService.protect_field(model, field)` marks a field and makes its two
permissions; nobody holds them yet, so from then on only the superuser reads
the field until a bundle holding them is given out.
`unprotect_field(model, field)` deletes both, and every grant of them. Three
refusals hold beside the library's own permissions:

* **a field a scope rule reads is not protected** - the rule would tell
  whoever it reaches what the field holds. The rules are named, and changed
  first. A rule on a field protected some other way - in code, after it was
  saved - reaches nothing, as any rule that no longer checks out;
* **nobody unprotects a field they do not hold both permissions of** - it
  would give them a field they were never given (`not_held`);
* **a field protected in code is unprotected in code**.

---

## 11. Layer 4: roles (optional)

`clearance.roles` keeps roles in the database, made in the admin site:

* **A role** is a code and a name in every language. People are given roles
  in the admin site (`RoleAssignment`), and a person may have several.
* **A ceiling** is the permissions a role may ever hold - or none, for a role
  that is not limited. What a person is allowed is what they hold, within the
  union of their roles' ceilings, applied in the backend after everything, so
  no bundle, grant or starting bundle gets past it. **Changing a ceiling
  needs `clearance.role_ceiling_edit`**, which only the superuser holds until
  given it - so administrators who manage bundles cannot widen what a role
  may hold.
* **Starting bundles**: `RoleBundle` gives everybody with a role a bundle.
* **From code**, roles, ceilings and starting bundles can be written in the
  `ACCESS` file instead (5.8), and the admin site shows them read only.
* **Elsewhere**: a project that keeps roles on its user model - a `role`
  column, `is_staff`, Django groups - reads them with `AttributeResolver` or a
  resolver of its own instead.
* **In a policy**, `has_role(user, *roles)` answers whose job an act is.

### 11.1 How a ceiling works

A person's ceiling is the union of their roles' ceilings. A person with no
role has none, and nor does a person with any role that is not limited: roles
limit, they do not stand in for bundles. A new role is limited and permits
nothing, so giving it to somebody takes everything from them until its
ceiling is set - the safe way round.

The ceiling and the starting bundles are conditions inside the queries the
backend and the grants already make (`clearance.limits`), so a person with
roles costs nothing more to ask about. The core imports nothing from
`clearance.roles`: the app puts them in force when it starts.

`AttributeResolver` reads a field of the user model - a column, never a
property - so that it can be read inside the same query. Anything else is a
resolver of the project's own, answering with querysets.

### 11.2 Changing roles

Every change goes through `RoleService`, under the core's rules and two more:

* **a ceiling is changed only with `role_ceiling_edit`** - setting one,
  removing one, and anything that lifts one from somebody: deleting a limited
  role, taking a limited role away from a person, or giving a person under a
  ceiling a second role that widens it - one that is not limited lifts it
  altogether;
* **nobody changes what their own role holds** - its ceiling, its starting
  bundles, or whether it exists.

Starting bundles are given like bundles: only by somebody holding what they
give. Roles read from the user model are given there, not here.

---

## 12. The safety rules

The admin site manages everything, so whoever may manage access must not be
able to give themselves everything. Every change - on a page or in code -
goes through `AccessService`, which refuses:

* **a change to your own access** - your bundles, grants, revocations, roles,
  or a bundle you hold. Somebody else who manages access does it, or the
  superuser;
* **giving what you do not hold** - putting a permission in a bundle, giving
  a bundle holding it, or granting it, when you do not hold it yourself; and
  **with a scope you do not hold it with**, unless you hold it with `all` -
  or a colleague could hand it back to you. Giving back a permission that
  was taken from somebody is giving it;
* **a change after which nobody but the superuser could manage access** -
  the last holder of `permission_edit` losing it;
* **a change to your own access** reaches a bundle you start with by your
  role, as one you were given;
* **a change to the rows of a rule scope your own grants are in**, or one
  granting a permission you do not hold on every row (9.2);
* **unprotecting a field you do not hold both permissions of** (10.4);
* **releasing a status action's value, or deleting it, without holding it on
  every row; letting one write from more values** (8.1);
* **changing what the `ACCESS` file owns** - anybody, the superuser too; only
  the sync changes it (5.8);
* **lifting a ceiling from anybody without `role_ceiling_edit`, or changing
  what your own role holds** (11.2);
* **a widened ceiling**, without `role_ceiling_edit`;
* **changing or deleting an account that holds more than you** - a
  permission you do not hold, a wider scope of one, or the superuser's flag.
  Setting an account's password is signing in as it.

Every refusal says which rule, and every change is a signal.

---

## 13. From a view to a policy

### 13.1 DRF

`ModelPolicyPermission` finds the view's model - from `queryset`, or a
`get_queryset()` written for the view - and asks that model's policy.
`PolicyPermission` asks the policy the view names in `policy`, for a view
with no model. Both map `list`/`retrieve` to `can_list`/`can_view`, `create`
to `can_create`, `update`/`partial_update` to `can_edit`, `destroy` to
`can_delete`, an `@action` to its found permission or the policy's
`custom_actions`, and an `APIView` by its HTTP method - `policy_action`
naming a different one; a method nobody maps is refused. The object level
uses the same table, with the object.

**On every serializer, a write is guarded.** Before the serializer runs, a
`create` or an `edit` sending a value the person may not write - a protected
field, a value a status action claims - is refused with a 400 naming the
field, so a serializer written without the library cannot write what it
should not. `ProtectedFieldsSerializerMixin` refuses the same way on its own,
for a serializer used outside such a view; it reads the person from the
request, or from `context['user']`, and refuses to be built with neither.

Reading has no such backstop - a permission class cannot change an answer -
so E003 refuses, at start-up, a view asking a model's policy whose serializer
would show every field. It holds for every model, not only one protecting
fields today: a field protected tomorrow in the admin site would otherwise be
shown by a serializer nobody changed.

### 13.2 Django views

`PolicyRequiredMixin` reads the action off the view - `ListView` `list`,
`DetailView` `view`, `CreateView` `create`, `UpdateView` `edit`,
`DeleteView` `delete` - or takes `policy_action`; a view it cannot read is
`ImproperlyConfigured`. Every view asks first with no object, in
`dispatch`; a view with an object asks again with it. `policy` may be left
out, and the model's is asked.

---

## 14. The admin site

Built on Django's own admin: its look, its dark mode, its right-to-left
layout when the language is Persian. No build step - templates, a stylesheet
and plain scripts.

| page | what the administrator does there |
|---|---|
| **Overview** | sees the bundles, roles, people with access, and what `clearance_check` found |
| **Bundles** | makes and changes a bundle as a **grid**: a model in each row, an action in each column, a tick, and a scope beside each ticked permission; gives it to people |
| **Row scopes** | builds a rule scope for a model, sees the code scopes beside it, and which grants use each |
| **Protected fields** | marks and unmarks fields, model by model |
| **Actions** | makes status actions; sees the actions found in the code, and the ones gone from it |
| **Roles** | makes roles, their starting bundles, and - with `role_ceiling_edit` - their ceilings |
| **People** | a person's whole standing: roles, bundles, direct grants with scopes, revocations with why - and what they end up allowed, with where each permission came from |
| **Permissions** | every permission, read only, with who holds it and how |

Every page writes through `AccessService` under the safety rules, and needs
the library's own permissions: `permission_view` to look, `permission_create`,
`_edit` and `_delete` to change.

What the `ACCESS` file or the code declares is shown as *declared in code*,
read only: changed in the admin site, it would come back on the next sync.
Without `django.contrib.admin`, none of these pages exist and nothing else
changes.

### 14.1 Every page of the admin site

A project uses the library's site by naming its admin app in place of
Django's - and nothing else in the project changes:

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
]
```

`ClearanceAdminSite` gives every `ModelAdmin` it registers, and every inline
of one, the library's hooks, so a project's admin classes stay exactly as
Django documents them:

* **who** - `has_view_permission` and the rest ask the model's policy, with
  the object when there is one;
* **which rows** - the change list, and every object opened, come from the
  rows the person reaches;
* **which fields** - a protected field the person may not read is left out of
  the form, the list, the search, the filters and the ordering - searching
  or sorting by it would tell what it holds; one they may read but not write
  is read only, in the form and in `list_editable`; a field a status action
  writes offers only the values they may set;
* **which actions** - an admin action the project wrote is offered only to
  whoever holds its permission, and runs only over the selected rows its
  scope reaches; one naming Django's `permissions=` is Django's to offer, and
  runs over the rows those permissions reach; and `delete_selected` runs over
  the rows the person may delete;
* **what is written** - a row added or changed stays among the rows the
  person may write (9.5). An inline and the editable list show the rows the
  person may *view*: one they may not edit is locked there, and one they may
  not delete is not deleted.

On the user model, a person's groups and permissions are read only - they are
changed on the people page, under the safety rules - and so is a field the
role resolver reads roles from. Only the superuser makes somebody a superuser,
and only the superuser changes or deletes a superuser's account, password
included: whoever sets it signs in as them. Switching off or deleting the last
person able to manage access is refused there as everywhere. Django's own
group page is taken away: a bundle
is a group, and that page wrote round every rule. An admin site that is not
the library's is refused at start-up (E016); a project with a site of its own
subclasses `ClearanceAdminSite`.

### 14.2 The pages

* **Row scopes** - every scope each model offers, in code or as a rule, with
  the grants using it, and a rule that reaches nothing marked. The rule
  builder offers the fields a rule may read - the model's own, and one
  relation further, never a protected field or the password - and a script
  adds and removes conditions; without the script the page still works,
  three conditions at a time. Every condition is checked on saving, and each
  one wrong is named.
* **Protected fields** - each model's fields, which are protected and how -
  in code, or here - and their two permissions.
* **Actions** - status actions made in two steps, the model and then its
  field, so the values are offered rather than typed; the actions found in
  the code; and the permissions nothing checks any more.
* **Roles** - with `clearance.roles`: every role, and each one's name,
  ceiling, starting bundles and people; a person's page shows their roles,
  the bundles they start with, and what their ceiling stops.

Each is a `PageSet`, mounted beside the others; every one of them writes
through the services. No page is wider than the screen, in either
direction - a wide table scrolls in its own box - and a browser test
(`nox -s browser`) holds that, the rule builder's script, and Persian read
right to left.

### 14.3 What the database says is wrong

`clearance_check` - and the overview page - say what only the database can
tell. **Errors** fail the command, because each is something made to give
access that now gives none, silently: a rule scope that no longer checks out,
a status action whose field or values are gone, a grant whose scope its model
offers no more. **Warnings** are listed without failing: a grant with no
scope on a model whose default reaches no rows, and a permission nothing
accounts for - an action gone from the code, or one made by hand.

### 14.4 Names in every language

A permission, a bundle or a role reads, in the reader's language: the name
an administrator gave it in that language - or in its base, `fa` for
`fa-ir` - else what the code says in that language (`build_permissions`'
labels, which the project's own catalogue translates), else its row. Without
`clearance.translations` only the last two apply.

The names are one table, keyed by what each names: a table per kind would
tie the app to every app whose things it names, and a project without roles
would not start. A name goes when the thing it names is deleted. A page reads
all the names of its language in one query (`labels_in()`), and every access
page names things through it; the names page names one thing in every
language of `LANGUAGES`, under `permission_edit`.

---

## 15. Settings

All under `CLEARANCE`; the default needs none of it. A key the library does
not know is refused (E011).

| key | default | meaning |
|---|---|---|
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AssignmentResolver'` | where a person's roles are read from |
| `ROLE_ATTRIBUTE` | `'role'` | what `AttributeResolver` reads |
| `ACCESS` | `None` | the access declared in code - bundles, roles, ceilings, status actions - applied by `clearance_sync` |
| `SYNC_ON_MIGRATE` | `False` | run `clearance_sync` once at the end of a forward `migrate` |
| `RULE_DEPTH` | `3` | how many relations a rule's field may cross |

---

## 16. Models

| app | model | holds |
|---|---|---|
| `clearance` | `ScopeGrant` | `group` or `user` (exactly one), `permission`, `scope` |
| `clearance` | `PermissionRevocation` | `user`, `permission`, `revoked_by`, `reason`, `revoked_at` |
| `clearance` | `ScopeRule` | `content_type`, `code`, `name`, `match` (all or any) |
| `clearance` | `ScopeCondition` | `rule`, `position`, `field`, `operator`, `source` (a constant, a list, the person's, none), `person` |
| `clearance` | `ScopeConditionValue` | `condition`, `position`, `value` - a constant, in words |
| `clearance` | `ProtectedField` | `content_type`, `field` - with the two permissions it made |
| `clearance` | `StatusAction` | `content_type`, `code`, `name`, `field` - with its permission |
| `clearance` | `StatusActionValue` | `action`, `end` (to or from), `position`, `value` |
| `clearance` | `Declared` | what the `ACCESS` file owns - a bundle, a role, a status action - so a sync knows what it may delete, and the admin site shows it read only |
| `clearance.roles` | `Role` | `code`, `name`, `limited` |
| `clearance.roles` | `RoleAssignment` | `user`, `role`, `assigned_by`, `assigned_at` |
| `clearance.roles` | `RoleCeiling` | `role`, `permission` |
| `clearance.roles` | `RoleBundle` | `role`, `group` |
| `clearance.translations` | `Translation` | `content_type`, `object_pk`, `language`, `name`, `description` - of a permission, a bundle or a role |

Every foreign key to a person is `settings.AUTH_USER_MODEL`.

---

## 17. System checks

| id | when |
|---|---|
| `clearance.E001` | `ACCESS` cannot be read, has a section no installed app reads, or says something that cannot be - a permission not named `app_label.codename`, a model not installed, a status action's field or value its model does not have |
| `clearance.E002` | a `ScopedQuerySet`'s `scopes` and its `scope_<x>` methods disagree, or its `default_scope` is not offered |
| `clearance.E003` | a DRF view asking a model's policy serializes the model without leaving out its protected fields |
| `clearance.E006` | `ClearanceBackend` is not in `AUTHENTICATION_BACKENDS` |
| `clearance.E007` | `ModelBackend`, or a backend built on it and not on the library's, is beside `ClearanceBackend` - it would hand back every revocation |
| `clearance.E008` | `clearance.roles` or `clearance.translations` is installed without `'clearance'`, or before it |
| `clearance.E009` | a `PolicyRequiredMixin` view, or a DRF view guarded by a policy, cannot ask one |
| `clearance.E010` | `ROLE_RESOLVER` or `ROLE_ATTRIBUTE` cannot be used |
| `clearance.E011` | `CLEARANCE` is not a dictionary, has a key the library does not know, or a value it cannot use - `RULE_DEPTH` below one |
| `clearance.E012` | a field protected in code is not a field of its model, or cannot be protected - the primary key, the password, a relation of another model - or its permission is another model's too |
| `clearance.E013` | an action found in the code cannot make a permission - its policy has no model, or the name is too long |
| `clearance.E014` | a model declares its permissions with `build_permissions` but keeps Django's own - `default_permissions = ()` is missing |
| `clearance.E015` | a status action declared in code names a field or a value its model does not have |
| `clearance.E016` | an admin site is not the library's: its pages would not ask the policies, and would show every protected field |

E004 and E005 are retired. E004 refused a scoped view over a plain manager,
and every queryset can be scoped now; E005 checked ceilings written in code,
and ceilings are in the database now.

`clearance_check` (14.3), which reads the database, lists grants with no scope, rule
scopes and status actions whose fields are gone, actions gone from the code,
and permissions nobody holds.

---

## 18. Signals

Each sent after the transaction commits, with the person or bundle, what
changed and `actor`: `bundle_created`, `bundle_changed`, `bundle_deleted`,
`bundle_given`, `bundle_taken`, `permission_granted`, `permission_revoked`,
`permission_restored`, `scope_changed`, `scope_rule_saved`,
`scope_rule_deleted`, `field_protected`, `field_unprotected`,
`status_action_saved`, `status_action_deleted`, `actions_found`, and with
`clearance.roles`, `role_saved`, `role_deleted`, `role_assigned`,
`role_unassigned`, `ceiling_changed`; and with `clearance.translations`,
`name_changed`.

---

## 19. Compatibility

| | supported | tested in CI |
|---|---|---|
| Python | 3.11 - 3.14 | every one |
| Django | 5.2 LTS, 6.0, 6.1 | each with every Python it supports |
| Django REST framework | 3.16 and later, optional | the latest |
| Database | any Django supports | PostgreSQL and SQLite |
| Browser, for the admin site | what Django's admin supports | the latest Chromium, by Playwright |

---

## 20. Conventions for this repository

* **English only in the code**; every message marked for translation, the
  Persian in `src/clearance/locale/fa/`.
* **Documentation in English and in Persian**, changed together.
* **Every module's docstring says why it exists**; every rule, what would go
  wrong without it.
* **Tests are named after the behaviour they hold**; cost is counted with
  `django_assert_num_queries`; the admin site's pages are tested in a browser.
* **ruff** and **mypy** (strict); one stage per pull request.

---

## 21. Stages

| stage | delivers | |
|---|---|---|
| 0 | the design | done |
| 1 | the skeleton and CI | done |
| 2 | permissions, policies, the registry | done |
| 3 | settings, Django views, the decorator, the checks - built around roles | done; reworked in 3b |
| **3b** | layers 1 and 2 at their core: default and custom permissions, `ModelPolicy`, `ScopeGrant`, `PermissionRevocation`, `ClearanceBackend`, `grants`, `AccessService` with **the safety rules**, the library's own permissions, code scopes and `visible_to(user, action)`, scope-aware hooks; the role code from stage 3 moves to stage 9 | |
| 4 | the rule builder: `ScopeRule`, its conditions checked and turned into `Q` | |
| 5 | protected fields: in code and in the database, under the safety rules; forms, views, templates and code - the admin site's door with the admin site, in stage 8 | |
| 6 | actions: status actions, in code and in the database, under the safety rules, and in forms; actions found in Django's views; a policy deciding an action with no hook by its permission | |
| 7 | DRF: `ModelPolicyPermission`, `PolicyPermission`, the viewsets, the serializer mixin refusing protected fields and status values, `@action`s found, their checks | |
| 8 | the admin site, part one: overview, bundles as a grid, people, permissions; every `ModelAdmin` asking `permission_for`, hiding and locking protected fields, narrowing status values, and offering its actions to whoever holds them | |
| 9 | `clearance.roles`: roles, ceilings, starting bundles, resolvers - and their pages | |
| 10 | access as code: the `ACCESS` file, `clearance_sync` with `--dry-run` and `--check`, `SYNC_ON_MIGRATE`, read only in the admin site | |
| 11 | the admin site, part two: the rule builder, protected fields and actions pages; right to left; browser tests; `clearance_check` and the overview's findings | |
| 12 | `clearance.translations` | |
| 13 | documentation, an example project, the Persian catalogue | |
| 14 | used in iranbobco; `0.1.0` tagged, made public, published | |

---

## 22. What this edition changes in what is built

* **Stage 2's permissions** gain the default ones: `permission_for(model,
  action)` answers both, and the policy asks it.
* **Stage 3** keeps its settings reader, `PolicyRequiredMixin`, the decorator
  and the checks. Its scoping by role becomes scoping by grant, and its
  resolvers move to `clearance.roles`.

## 23. After 0.1

* **A grant on one row** - "Ali may edit order 42".
* **Protected fields scoped by row** - the price of their own branch's orders.
* **Rules joined at several levels** - (A and B) or C.
* **REST endpoints** for an access screen and for "what may I do".

---

## 24. Decisions

Made by the owner.

1. Every import names its module.
2. The licence holder is amir mohammad kashanchian.
3. The oldest Python is 3.11.
4. *(amended by 27)* The default role resolver reads `user.role`.
5. Django's own views get the same bridge as DRF.
6. The admin site shows permissions and makes bundles.
7. Permissions and bundles can be named in any language, in 0.1.
8. Access bundles are the core; a project needs no roles.
9. A row scope is chosen per permission within a bundle.
10. Roles limit, and may start a person with bundles - which the ceiling
    limits too.
11. Fields can be protected, each with its own view and edit permission.
12. A permission given with no scope reaches the model's `default_scope` -
    and no rows when the developer named none.
13. In 0.1, a field's permissions are the person's, not scoped by row.
14. *(replaced by 23)* Ceilings are written in code.
15. A protected field is left out when it may not be read, and a value sent
    for it is refused when it may not be written.
16. `'clearance'` is one app with models, holding layers 1 to 3.
17. Every layer is optional; the one requirement is `ClearanceBackend`.
18. **Default and custom are chosen per model**: Django's own permissions by
    default, `build_permissions` for a model that declares its own.
19. **The admin site does everything the library can do.**
20. **Status actions** are made in the admin site, without code.
21. **Actions are found in the code** - DRF `@action`, `policy_action`,
    `@policy_required`, admin actions - and get their permissions on
    `migrate`.
22. **Row scopes are built in the admin site** from simple rules, in 0.1,
    beside the code scopes.
23. **Roles and ceilings are kept in the database** and made in the admin
    site; **changing a ceiling needs `role_ceiling_edit`**, which only the
    superuser holds by default.
24. **The library's own permissions** - `permission_view`, `_create`, `_edit`,
    `_delete` - are held by the superuser by default.
25. **The safety rules are in 0.1**, because the admin site manages access.
26. **Every kind of DRF and Django view works**, `ModelViewSet` among them.
27. **Decision 4 amended:** with roles made and given in the admin site, the
    default resolver reads the `RoleAssignment` rows the admin site writes;
    `AttributeResolver`, reading `user.role`, is for a project that keeps
    roles on its user model.
28. **A rule cannot read a protected field**, nor the user's password, and
    reaches at most three relations away.
29. **The password field and the primary key cannot be protected.**
30. **No permission is typed by an administrator**: actions are status actions
    or found in the code, so every permission in the admin site is checked
    somewhere.
31. **A model keeping Django's permissions beside its own is refused** (E014),
    and Django's own admin pages ask `permission_for`.
32. **Status actions can be declared in code** as well as made in the admin
    site.
33. **Access can be written as code** - the `ACCESS` file - and applied by
    `clearance_sync`, with `--dry-run` and `--check`.
34. **What code declares is read only in the admin site**; what the admin
    site makes, code does not touch.
35. **The admin site is optional**: without it the library works whole.
36. **`migrate` makes the permissions; `clearance_sync` gives access.**
    `SYNC_ON_MIGRATE` joins them for a project that wants one command.
37. **A field that may not be read may not be written**, and a field's
    permission is given with no scope.
38. **A field a scope rule reads is not protected until the rule changes**;
    unprotecting a field needs both of its permissions.
39. **An action with no hook is decided by its permission and its scope**;
    only a name that could never be a permission is an error.
40. **A status action's value is released, or the action deleted, only by
    somebody holding it on every row**; nobody widens where an action they
    hold writes from.
41. **On every DRF serializer, a write is guarded** by the permission class,
    refused with a 400 naming the field.
42. **A DRF view asking a model's policy protects its serializer** (E003), for
    every model - a field can be protected later, in the admin site.
43. **`custom_actions` is read everywhere a policy is asked**, not only by
    DRF; an action it maps is the hook's, and no permission is made for it.
44. **The admin site is the library's**, named in `INSTALLED_APPS` in place of
    Django's, and gives every `ModelAdmin` its hooks with no mixin written;
    any other admin site is refused (E016).
45. **On the user page, a person's groups and permissions are read only**,
    changed on the people page under the safety rules; only the superuser
    makes a superuser, changes or deletes a superuser's account, or writes a
    field roles are read from; and the last person able to manage access is
    not switched off or deleted there.
46. **An admin action naming Django's `permissions=` is Django's to offer**,
    and runs over the rows those permissions reach; any other is found, needs
    its own permission, and runs over the rows its scope reaches.
47. **A person with no role, or with any role that is not limited, has no
    ceiling**; a new role is limited and permits nothing until its ceiling is
    set.
48. **Lifting a ceiling from anybody needs `role_ceiling_edit`** - changing
    one, deleting a limited role, taking a limited role away - and nobody
    changes what their own role holds.
49. **Roles are read inside the query**: `AttributeResolver` reads a field,
    and the core puts roles in force through `clearance.limits` without
    importing them.
50. **The library's apps set their own primary key**, so a project's
    `DEFAULT_AUTO_FIELD` never asks it to make a migration for them.
51. **The `ACCESS` file owns what it names, and nothing else**: a sync deletes
    only what the file once named, and takes over what the admin site made
    once the file names it.
52. **What the file owns is changed only by the sync** - refused to every
    person, the superuser too.
53. **Who has a bundle or a role is not the file's to say**; it stays in the
    admin site.
54. **`clearance_check` fails on what gives no access silently**, and warns of
    what may not be meant.
55. **A page works without its script**; the script only makes it easier.
56. **No page is wider than the screen, in either direction**, and a browser
    test holds it.
57. **One table names permissions, bundles and roles**, keyed by what it
    names, so the translations app needs no other app.
58. **A name reads from the reader's language, then its base, then the
    code, then the row.**
59. **No JSON column.** A rule's conditions and a status action's values are
    rows of their own, which the database constrains and joins; the rules of
    a request are still read in one query.
60. **Each app ships its own Persian catalogue, compiled and committed**, so
    installing the library needs no gettext; `nox -s messages` fails when a
    marked string is missing from one, and a test when a translation is
    empty, fuzzy, loses a placeholder or was not compiled.
61. **The example project is run by the suite**, on every Python and Django
    it supports: an example that no longer works teaches something the
    library does not do.
62. **Nothing a `models.py` may import reads the user model**, and nothing
    DRF's settings import imports DRF's views - the example found both, with
    its user model in the same app as its orders and DRF's default
    permission set as the guide says.
63. **An account is changed only by its equal or more.** Whoever may change
    users could otherwise set the password of somebody who manages access,
    and sign in as them. It is asked in `policy.allows`, so every door asks it.
64. **A delete takes nothing its maker may not delete.** A cascade into a
    model the library guards is asked as the delete itself; another model's
    rows go as Django sends them, as its admin site does.
