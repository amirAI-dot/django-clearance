# سیگنال‌ها

هر تغییری در دسترسی اعلام می‌شود، برای سابقه‌ای که خود پروژه نگه می‌دارد. هر سیگنال
**بعد از commit شدن تراکنش** فرستاده می‌شود، پس گیرنده هیچ‌وقت تغییری را که برگشت
خورده ثبت نمی‌کند، و هر کدام کنار آنچه تغییر کرده `actor` را هم دارد - کسی که تغییر را
داده، و `None` برای خود سیستم.

```python
from django.dispatch import receiver

from clearance.signals import permission_revoked


@receiver(permission_revoked)
def record(sender, actor, person, permission, reason, **kwargs):
    AuditEntry.objects.create(who=actor, whom=person, what=f'revoked {permission}: {reason}')
```

## `clearance.signals`

`AccessService` آن‌ها را می‌فرستد.

| سیگنال | همراه دارد |
|---|---|
| `bundle_created` | `bundle`، `grants` - `{permission: scope}` |
| `bundle_changed` | `bundle`، `before`، `after` - هر کدام `{permission: scope}` - و `name` |
| `bundle_deleted` | `name`، `grants`، `people` - کسانی که به آن‌ها می‌رسید |
| `bundle_given` | `person`، `bundle` |
| `bundle_taken` | `person`، `bundle` |
| `permission_granted` | `person`، `permission`، `scope` |
| `permission_revoked` | `person`، `permission`، `reason` |
| `permission_restored` | `person`، `permission` |
| `scope_changed` | `person`، `permission`، `before`، `after` |
| `scope_rule_saved` | `rule`، `created` - اینکه تازه است یا نه |
| `scope_rule_deleted` | `model`، `code`، `name` |
| `field_protected` | `model`، `field`، `permissions` - `{'view': ..., 'edit': ...}`، تازه ساخته‌شده |
| `field_unprotected` | `model`، `field`، `permissions` - دو مجوزی که همراهش حذف شدند |
| `status_action_saved` | `action`، `created` - اینکه تازه است یا نه |
| `status_action_deleted` | `model`، `code`، `name` |
| `actions_found` | `permissions` - آن‌هایی که `migrate` همین حالا برای اکشن‌های پیداشده در کد ساخت؛ `actor` برابر `None` است |

## `clearance.roles.signals`

`RoleService` آن‌ها را می‌فرستد، وقتی `clearance.roles` نصب باشد.

| سیگنال | همراه دارد |
|---|---|
| `role_saved` | `role`، `created` - اینکه تازه است یا نه |
| `role_deleted` | `code`، `name` |
| `role_assigned` | `person`، `role` |
| `role_unassigned` | `person`، `role` |
| `ceiling_changed` | `role`، `before`، `after` - هر کدام مجوزهایی که اجازه می‌دهد، یا `None` برای بدون سقف |

## `clearance.translations.signals`

`TranslationService` آن را می‌فرستد، وقتی `clearance.translations` نصب باشد.

| سیگنال | همراه دارد |
|---|---|
| `name_changed` | `thing`، `language`، `before`، `after` - هر کدام `(name, description)`، یا `None` |
