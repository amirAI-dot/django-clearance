# Signals

Every change to access is announced, for a project's own audit trail. Each
signal is sent **after the transaction commits**, so a receiver never records
a change that was rolled back, and each carries `actor` - who made the change,
`None` for the system - beside what changed.

```python
from django.dispatch import receiver

from clearance.signals import permission_revoked


@receiver(permission_revoked)
def record(sender, actor, person, permission, reason, **kwargs):
    AuditEntry.objects.create(who=actor, whom=person, what=f'revoked {permission}: {reason}')
```

## `clearance.signals`

Sent by `AccessService`.

| signal | carries |
|---|---|
| `bundle_created` | `bundle`, `grants` - `{permission: scope}` |
| `bundle_changed` | `bundle`, `before`, `after` - each `{permission: scope}` - and `name` |
| `bundle_deleted` | `name`, `grants`, `people` - whom it reached |
| `bundle_given` | `person`, `bundle` |
| `bundle_taken` | `person`, `bundle` |
| `permission_granted` | `person`, `permission`, `scope` |
| `permission_revoked` | `person`, `permission`, `reason` |
| `permission_restored` | `person`, `permission` |
| `scope_changed` | `person`, `permission`, `before`, `after` |
| `scope_rule_saved` | `rule`, `created` - whether it is new |
| `scope_rule_deleted` | `model`, `code`, `name` |
| `field_protected` | `model`, `field`, `permissions` - `{'view': ..., 'edit': ...}`, just made |
| `field_unprotected` | `model`, `field`, `permissions` - the two deleted with it |
| `status_action_saved` | `action`, `created` - whether it is new |
| `status_action_deleted` | `model`, `code`, `name` |
| `actions_found` | `permissions` - those `migrate` just made for actions found in the code; `actor` is `None` |

## `clearance.roles.signals`

Sent by `RoleService`, with `clearance.roles` installed.

| signal | carries |
|---|---|
| `role_saved` | `role`, `created` - whether it is new |
| `role_deleted` | `code`, `name` |
| `role_assigned` | `person`, `role` |
| `role_unassigned` | `person`, `role` |
| `ceiling_changed` | `role`, `before`, `after` - each the permissions it allows, or `None` for no ceiling |

## `clearance.translations.signals`

Sent by `TranslationService`, with `clearance.translations` installed.

| signal | carries |
|---|---|
| `name_changed` | `thing`, `language`, `before`, `after` - each `(name, description)`, or `None` |
