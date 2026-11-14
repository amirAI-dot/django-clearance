# Settings

Everything the library reads is under one setting, `CLEARANCE`, and a project
needs none of it: every key has a default.

```python
CLEARANCE = {
    'ACCESS': 'config.access.ACCESS',
    'SYNC_ON_MIGRATE': True,
}
```

A key the library does not know is refused at start-up (E011) rather than
ignored: a misspelled `SYNC_ON_MIGRAT` that is quietly ignored is a
deployment whose access never changes, and nobody can tell why.

| key | default | what it is |
|---|---|---|
| `ACCESS` | `None` | the dotted path of the [`ACCESS` file](access-file.md) - bundles, status actions and roles written as code |
| `SYNC_ON_MIGRATE` | `False` | apply the `ACCESS` file once at the end of every forward `migrate` |
| `RULE_DEPTH` | `3` | how many relations a rule scope's field may cross - a whole number from 1 |
| `PERSON_FIELDS` | `()` | the fields of the user model the project's code scopes read - locked on a person's own account |
| `CASCADE_UNASKED_APPS` | `()` | the apps whose rows a delete takes with it without asking for their `delete` |
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AssignmentResolver'` | with `clearance.roles`: where a person's roles are read from |
| `ROLE_ATTRIBUTE` | `'role'` | the field of the user model `AttributeResolver` reads a role's code from |

## `PERSON_FIELDS`

A rule scope that reads a field of the person - "the person's branch" - is
known to the library, and nobody writes that field on their own account: it
would be changing their own access. A scope in code is not known to it, so a
project names the fields its code scopes read:

```python
CLEARANCE = {'PERSON_FIELDS': ['branch']}
```

## `CASCADE_UNASKED_APPS`

Deleting a row asks, for every row a cascade would take, whether the person
may delete it too. An app keeping a token or an address for each account,
whose `delete` nobody is given, would make every account undeletable:

```python
CLEARANCE = {'CASCADE_UNASKED_APPS': ['authtoken']}
```

A model the library guards - one with scopes, or declared permissions - is
asked all the same.

## Django's own settings

| setting | what the library needs |
|---|---|
| `INSTALLED_APPS` | `'clearance.admin.apps.ClearanceAdminConfig'` in place of `'django.contrib.admin'`; `'clearance'`, then the optional `'clearance.roles'` and `'clearance.translations'` |
| `AUTHENTICATION_BACKENDS` | `'clearance.backends.ClearanceBackend'`, and not `ModelBackend` beside it |
| `REST_FRAMEWORK` | with DRF, `'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission']` |
| `LANGUAGES` | with `clearance.translations`, the languages a name is given in |
