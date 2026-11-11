# The guide

[فارسی](guide.fa.md)

How to use django-clearance in a project, from installing it to the last
optional app. Why it is built the way it is lives in the
[design](design.md); a project that uses every part of it is in
[`example/`](../example/README.md).

---

## 1. What it does

Four layers, each answering one question, and each usable without the next:

| layer | the question | where it is decided |
|---|---|---|
| bundles | which permissions does this person hold? | the admin site, or the `ACCESS` file |
| row scopes | which rows does a permission reach? | the scope chosen beside each permission |
| protected fields | which fields may they read, and write? | a field's own two permissions |
| roles, optional | what can this person never hold, whatever they are given? | a role's ceiling |

**Denied by default.** A person holds nothing they were not given, a
permission reaches no rows until a scope says which, and a view that cannot
say which policy to ask is refused at start-up.

---

## 2. Installing it

```bash
pip install 'django-clearance[drf]'    # or django-clearance, without DRF
```

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
    'clearance',
    'clearance.roles',          # optional: roles and ceilings
    'clearance.translations',   # optional: names in every language
]

# In place of django.contrib.auth.backends.ModelBackend (E006, E007).
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

# With DRF: every view asks the model's policy, unless it names another.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

```bash
python manage.py migrate
```

The optional apps come after `'clearance'` (E008). The admin app is
optional too; without it, no access page exists and nothing else changes.

---

## 3. Permissions

A model keeps Django's permissions - `shop.view_order`, `add_order`,
`change_order`, `delete_order` - and nothing needs to change. Or it declares
the library's, named after what is done rather than after Django's views:

```python
from clearance.permissions import DEFAULT_ACTIONS, build_permissions

class Order(models.Model):
    ...
    class Meta:
        default_permissions = ()        # E014 without it
        permissions = build_permissions(
            'order',
            _('orders'),
            actions=(*DEFAULT_ACTIONS, 'approve'),
            labels={'approve': _('Can approve or reject %(resource)s')},
        )
```

That is `shop.order_view`, `order_create`, `order_edit`, `order_delete` and
`order_approve`. `permission_for(Order, 'edit')` answers either style, so
nothing else in the project needs to know which a model keeps.

---

## 4. Bundles

A bundle is Django's `Group`: permissions given together, each with a scope.
They are made in the admin site - *Access*, *Bundles*, a grid with a model in
each row and an action in each column - or in code:

```python
from clearance.services import AccessService

access = AccessService(actor=request.user)

managers = access.create_bundle(
    'Branch managers',
    grants={'shop.order_view': 'branch', 'shop.order_edit': 'branch'},
)
access.give_bundle(person, managers)
access.revoke(person, 'shop.order_edit', reason='Under review')
```

`revoke` takes one permission from one person, whatever their bundles give,
and says why. Every change goes through `AccessService`, under the safety
rules (section 12), and sends a signal once it commits.

---

## 5. Row scopes

A scope says which rows a permission reaches. A model offers scopes in code,
and an administrator builds more from rules.

### 5.1 In code

```python
from clearance.querysets import ScopedQuerySet

class OrderQuerySet(ScopedQuerySet):
    scopes = {
        'own': _('Their own orders'),
        'branch': _("Their branch's orders"),
    }

    def scope_own(self, user):
        return Q(customer=user)

    def scope_branch(self, user):
        return Q(branch=user.branch_id)

class Order(models.Model):
    ...
    objects = OrderQuerySet.as_manager()
```

`all` is always offered. `default_scope` is what a grant with no scope
reaches - by default nothing. `OwnedQuerySet` is the common case written
once: `owner_path = 'customer'` gives the scope `own`.

### 5.2 As rules, in the admin site

*Access*, *Row scopes*, *Build*: a name, *all of* or *any of*, and
conditions - a field, an operator and a value, a constant or something of
the person's:

```text
branch      is          the person's branch
status      is one of   pending, approved
```

A rule is only ever a Django `Q`, checked when it is saved. It never reads a
protected field or the password, and crosses at most `RULE_DEPTH` relations.

### 5.3 Asking for rows

```python
Order.objects.visible_to(user, 'edit')     # the orders they may edit
visible(Order.objects.all(), user, 'view')   # the same, for any queryset
```

A person's grants and rules are read once per request, in a fixed number of
queries, however many lists the page shows.

---

## 6. Protected fields

A field read with one permission and written with another:

```python
permissions = build_permissions('order', _('orders'), protected_fields=('price',))
```

That adds `shop.order_view_price` and `shop.order_edit_price`. A field can
also be protected in the admin site, *Access*, *Protected fields*, with no
code. Either way, a field the person may not read is left out of every door:
DRF serializers, Django forms and templates, the admin site's forms, lists,
search, filters and ordering - and rules.

```python
readable_fields(user, Order)   # {'id', 'customer', 'branch', 'item', 'status'}
writable_fields(user, Order)
```

In a Django view, `ProtectedFieldsViewMixin` builds the form for the person
and gives the template `readable_fields`:

```django
{% if 'price' in readable_fields %}<td>{{ order.price }}</td>{% endif %}
```

---

## 7. Actions

### 7.1 Status actions

An action that writes values: only whoever may approve sets *approved* or
*rejected*, and only from *pending*.

```python
permissions = build_permissions(
    'order',
    _('orders'),
    actions=(*DEFAULT_ACTIONS, 'approve'),
    status_actions={
        'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
    },
)
```

Or in the admin site, *Access*, *Actions*, with no code. A value no action
claims is written by whoever may edit the row. Forms and serializers offer
only the values the person may write:

```python
writable_values(user, Order, 'status', order)   # {'pending', 'delivered'}
```

### 7.2 Actions found in the code

An `@action` on a viewset, an admin action, a view's `policy_action`: each
is an action, and `migrate` makes its permission.

```python
class OrderViewSet(ScopedModelViewSet):
    @action(detail=True, methods=['post'])
    def print_invoice(self, request, pk=None):    # shop.order_print_invoice
        ...
```

*Access*, *Actions* lists them, and the permissions nothing checks any more.

---

## 8. Policies

A model with no policy is asked through `ModelPolicy`: its permission, within
its scope. A policy is written only for a rule no permission can say:

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class OrderPolicy(BasePolicy):
    model = Order

    def can_edit(self, user, obj=None):
        if not self.has_within_scope(user, 'edit', obj):
            return False
        return obj is None or obj.status != 'delivered'

order_access = registry.register(OrderPolicy)
```

Register it where it is imported at start-up - the app's `ready()`. A hook is
`can_<action>`; `custom_actions` maps an action to a hook named otherwise.
Asked outside a view:

```python
order_access.policy.allows(user, 'edit', order)
order_access.policy.authorize(user, 'edit', order)    # PermissionDenied if not
```

---

## 9. Views

### 9.1 Django's views

```python
from clearance.views import PolicyRequiredMixin, ProtectedFieldsViewMixin, ScopedQuerySetMixin

class OrderEdit(ProtectedFieldsViewMixin, PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):
    queryset = Order.objects.all()
    fields = ('item', 'status', 'price')
```

The action is read off the view - `ListView` is `list`, `UpdateView` is
`edit` - or named with `policy_action`. A function view:

```python
@policy_required(order_access.policy, 'refund')
def refund(request, pk):
    ...
```

### 9.2 DRF

```python
from clearance.drf.viewsets import ScopedModelViewSet

class OrderViewSet(ScopedModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer       # written knowing nothing of the library
```

`ScopedModelViewSet` narrows the rows, asks the model's policy for each
action, and leaves out the fields the person may not read. A write naming a
field they may not write - or a status value they may not set - is a 400
naming the field. Each part works alone on any DRF view:
`ScopedQuerySetMixin`, `ModelPolicyPermission`, `ProtectedSerializerMixin`.
A view of no model names its policy:

```python
class OrderReport(APIView):
    permission_classes = (PolicyPermission,)
    policy = order_access.policy
    policy_action = 'report'
```

**A view that holds no record says so.** With `ModelPolicyPermission` as the
default, a view with no model and no policy is refused at start-up (E009) -
DRF's own `DefaultRouter` root view among them. Give it the permission it
needs:

```python
class ShopRouter(routers.DefaultRouter):
    class APIRootView(routers.APIRootView):
        permission_classes = (IsAuthenticated,)
```

---

## 10. The admin site

`ClearanceAdminConfig` replaces Django's admin site with the library's, and
a project's `ModelAdmin` classes stay as Django documents them. Every page
asks the model's policy, shows only the rows the person reaches, leaves out
or locks protected fields, offers only the status values they may write, and
offers an admin action only to whoever holds its permission.

Under *Access*:

| page | what is done there |
|---|---|
| Overview | the bundles, roles, people with access, and what `clearance_check` found |
| Bundles | a bundle as a grid, and who holds it |
| People | one person's whole standing, and where each permission came from |
| Permissions | every permission, and who holds it |
| Row scopes | the rule builder |
| Protected fields | marking fields, model by model |
| Actions | status actions; actions found in the code |
| Roles | with `clearance.roles` |

The pages need the library's own permissions: `clearance.permission_view` to
look, `permission_create`, `permission_edit` and `permission_delete` to
change. In Persian they read right to left.

---

## 11. Access as code

The bundles, status actions and roles a project always has can live in a
file, reviewed like code:

```python
# config/access.py
ACCESS = {
    'bundles': {
        'Branch managers': {'shop.order_view': 'branch', 'shop.order_approve': 'branch'},
        'Customers': {'shop.order_view': 'own', 'shop.order_create': 'own'},
    },
    'status_actions': {                  # for a model keeping Django's permissions
        'shop.Payment': {'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']}},
    },
    'roles': {                           # with clearance.roles
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.order_view', 'shop.order_create'],
            'bundles': ['Customers'],
        },
    },
}
```

```python
CLEARANCE = {'ACCESS': 'config.access.ACCESS', 'SYNC_ON_MIGRATE': True}
```

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

The file owns what it names and nothing else; the admin site shows it read
only. Who is given a bundle or a role stays in the admin site.

---

## 12. The safety rules

Every change - in the admin site, in code, from the `ACCESS` file - is
refused when it would let somebody give themselves more:

* nobody changes their own access, or a bundle or role they hold;
* nobody gives a permission or a scope they do not hold themselves;
* a change after which nobody could manage access is refused;
* what the `ACCESS` file owns is changed only in the file.

A refusal is `AccessRefused`, naming the rule. The superuser holds every
permission and reaches every row.

---

## 13. Roles

With `clearance.roles`, a role is what a person is: a customer, a branch
manager. It gives two things:

* **starting bundles** - everybody with the role holds them, without being
  given them one by one;
* **a ceiling** - the most they may ever hold, whatever a bundle or a grant
  gives them. A role with no ceiling limits nothing.

Roles are given in the admin site or with `RoleService(actor).assign(person,
role)`, and read by the resolver `ROLE_RESOLVER` names. `AttributeResolver`
reads them off the user instead - a field named by `ROLE_ATTRIBUTE`. In code:

```python
from clearance.roles.resolvers import has_role

has_role(user, 'manager')
```

---

## 14. Names in every language

The library's own pages, messages and permission names come in English and
Persian (`fa`); a project's own catalogue translates the labels it gives
`build_permissions`. With `clearance.translations`, an administrator also
names a permission, a bundle or a role in every language of `LANGUAGES`,
from its page:

```python
from clearance.labels import label_of, labels_in

label_of(bundle)                      # in the active language
labels = labels_in('fa')              # every name of a language, in one query
labels.of(permission)
```

```django
{% load clearance %}{{ bundle|label:labels }}
```

A name reads from the reader's language, then its base language, then what
the code says, then the row.

---

## 15. Checking it

At start-up, Django's system checks refuse what cannot work: a backend
missing or doubled, a view that cannot ask a policy, a serializer that would
show a protected field, an admin site that is not the library's. The full
list is in the design, section 17.

What only the database can tell, `clearance_check` says:

```bash
python manage.py clearance_check
```

**Errors** fail it - a rule scope that no longer checks out, a status action
whose field or values are gone, a grant whose scope the model no longer
offers - because each gives no access, silently. **Warnings** are listed: a
grant with no scope on a model whose default reaches no rows, and permissions
nothing accounts for.

---

## 16. Settings

All under `CLEARANCE`; none is needed.

| key | default | meaning |
|---|---|---|
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AssignmentResolver'` | where a person's roles are read from |
| `ROLE_ATTRIBUTE` | `'role'` | what `AttributeResolver` reads |
| `ACCESS` | `None` | the access declared in code, applied by `clearance_sync` |
| `SYNC_ON_MIGRATE` | `False` | run `clearance_sync` at the end of every forward `migrate` |
| `RULE_DEPTH` | `3` | how many relations a rule's field may cross |

A key the library does not know is refused (E011).

---

## 17. Signals

Each is sent once the change commits, with `actor` and what changed:
`bundle_created`, `bundle_changed`, `bundle_deleted`, `bundle_given`,
`bundle_taken`, `permission_granted`, `permission_revoked`,
`permission_restored`, `scope_changed`, `scope_rule_saved`,
`scope_rule_deleted`, `field_protected`, `field_unprotected`,
`status_action_saved`, `status_action_deleted`, `actions_found`; with
`clearance.roles`, `role_saved`, `role_deleted`, `role_assigned`,
`role_unassigned` and `ceiling_changed`; with `clearance.translations`,
`name_changed`.

```python
from clearance import signals

@receiver(signals.permission_revoked)
def tell_security(sender, person, permission, reason, actor, **kwargs):
    ...
```
