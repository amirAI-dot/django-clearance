# System checks

Django's system checks run at start-up - `runserver`, `migrate`, `check` -
and refuse what cannot work, before anybody finds it. Each is an error: the
project does not start until it is mended.

```bash
python manage.py check
```

| id | when |
|---|---|
| `clearance.E001` | `ACCESS` cannot be read, has a section no installed app reads, or says something that cannot be - a permission not named `app_label.codename`, a model not installed, a status action's field or value its model does not have |
| `clearance.E002` | a `ScopedQuerySet`'s `scopes` and its `scope_<x>` methods disagree, or its `default_scope` is not offered |
| `clearance.E003` | a DRF view asking a model's policy serializes the model without leaving out its protected fields |
| `clearance.E006` | `ClearanceBackend` is not in `AUTHENTICATION_BACKENDS` |
| `clearance.E007` | `ModelBackend`, or a backend built on it and not on the library's, is beside `ClearanceBackend` - it would hand back every permission taken away |
| `clearance.E008` | `clearance.roles` or `clearance.translations` is installed without `'clearance'`, or before it |
| `clearance.E009` | a `PolicyRequiredMixin` view, or a DRF view guarded by a policy, cannot ask one |
| `clearance.E010` | `ROLE_RESOLVER` or `ROLE_ATTRIBUTE` cannot be used |
| `clearance.E011` | `CLEARANCE` is not a dictionary, has a key the library does not know, or a value it cannot use |
| `clearance.E012` | a field protected in code is not a field of its model, or cannot be protected - the primary key, the password, a relation of another model - or its permission is another model's too |
| `clearance.E013` | an action found in the code cannot make a permission - its policy has no model, or the name is too long |
| `clearance.E014` | a model declares its permissions with `build_permissions` but keeps Django's own - `default_permissions = ()` is missing |
| `clearance.E015` | a status action declared in code names a field or a value its model does not have |
| `clearance.E016` | an admin site is not the library's: its pages would not ask the policies, and would show every protected field |

E004 and E005 are retired and never raised. E004 refused a scoped view over
a plain manager, and every queryset can be scoped now; E005 checked ceilings
written in code, and ceilings are in the database now.

## What only the database can tell

A system check sees the code. What the rows hold is
[`clearance_check`](commands.md#clearance_check)'s to say.
