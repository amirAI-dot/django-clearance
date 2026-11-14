# Reference

Everything the library offers, listed. The [guide](../guide.md) explains
how the parts fit; this section is for looking one up.

## Configuration

| page | what is there |
|---|---|
| [Settings](settings.md) | every key of `CLEARANCE`, with its default |
| [The `ACCESS` file](access-file.md) | bundles, status actions and roles written as code |
| [System checks](checks.md) | every `clearance.E0xx`, and what it refuses at start-up |
| [Management commands](commands.md) | `clearance_sync` and `clearance_check`, with their options |
| [Signals](signals.md) | every change to access, announced - and what each carries |
| [Models](models.md) | the tables the library keeps |
| [Template tags](template-tags.md) | `{% load clearance %}` |

## Python API

Read from the code itself, so it never falls behind it. The descriptions are
the code's own, in English.

| page | what is there |
|---|---|
| [Permissions](api/permissions.md) | `build_permissions`, `permission_for` |
| [Row scopes](api/querysets.md) | `ScopedQuerySet`, `OwnedQuerySet`, `SignedInReadQuerySet`, `visible` |
| [Policies](api/policies.md) | `BasePolicy`, `ModelPolicy`, the registry |
| [Services](api/services.md) | `AccessService` - every change to access |
| [Fields and values](api/fields.md) | protected fields, status actions, writes within scope |
| [Views](api/views.md) | Django's views and the decorator |
| [Django REST framework](api/drf.md) | permissions, serializers, viewsets |
| [The admin site](api/admin.md) | `ClearanceAdminSite` |
| [Roles](api/roles.md) | `RoleService`, the resolvers, `has_role` |
| [Names](api/names.md) | `label_of`, `labels_in`, `TranslationService` |
| [Extending it](api/extending.md) | the limits a layer above bundles installs, and the user protocol |
