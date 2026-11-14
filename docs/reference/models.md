# Models

The tables the library keeps beside Django's own. A bundle is Django's
`Group`, and a permission Django's `Permission` - the library adds what they
cannot hold. Every foreign key to a person is `settings.AUTH_USER_MODEL`, and
nothing is stored as JSON: every value is a row of its own.

Every change goes through the services, under the safety rules. Writing these
tables by hand walks round every rule.

## `clearance`

| model | holds |
|---|---|
| `ScopeGrant` | `group` or `user` - exactly one - `permission`, `scope`: the scope a permission is given in |
| `PermissionRevocation` | `user`, `permission`, `revoked_by`, `reason`, `revoked_at`: a permission taken from one person |
| `ScopeRule` | `content_type`, `code`, `name`, `match` - all or any: a rule scope |
| `ScopeCondition` | `rule`, `position`, `field`, `operator`, `source` - a constant, a list, the person's, none - `person`: one condition of a rule |
| `ScopeConditionValue` | `condition`, `position`, `value`: a constant, in words |
| `ProtectedField` | `content_type`, `field`: a field protected in the admin site, with the two permissions it made |
| `StatusAction` | `content_type`, `code`, `name`, `field`: a status action made in the admin site, with its permission |
| `StatusActionValue` | `action`, `end` - to or from - `position`, `value` |
| `Declared` | what the `ACCESS` file owns - a bundle, a role, a status action - so a sync knows what it may delete, and the admin site shows it read only |
| `Access` | no table: it carries the library's own permissions - `permission_view`, `_create`, `_edit`, `_delete` and `role_ceiling_edit` |

## `clearance.roles`

| model | holds |
|---|---|
| `Role` | `code`, `name`, `limited` |
| `RoleAssignment` | `user`, `role`, `assigned_by`, `assigned_at` |
| `RoleCeiling` | `role`, `permission`: one permission a limited role permits |
| `RoleBundle` | `role`, `group`: a starting bundle |

## `clearance.translations`

| model | holds |
|---|---|
| `Translation` | `content_type`, `object_pk`, `language`, `name`, `description` - of a permission, a bundle or a role |
