# Changelog

[فارسی](CHANGELOG.fa.md)

## Unreleased

Found by a security review of 0.1.0.

* **The page of a user opens in the admin site.** Adding or changing one was
  a server error with Django's `UserAdmin`, for everybody.
* **A superuser's account is the superuser's alone** to change or delete in
  the admin site - its password too. Before, anybody who could change users
  could set a superuser's password and sign in as them.
* **A field roles are read from is written by the superuser only** in the
  admin site, so nobody gives themselves a role with `AttributeResolver`. A
  resolver of the project's own names its fields with `RoleResolver.fields()`.
* **The last person able to manage access is not switched off or deleted** on
  the user page.

## 0.1.0 - the first release

Alpha: every part is built and tested, but not yet used in a project with
real models, so the API may still change before 1.0.

* **Bundles** - Django's groups, each permission given with a **row scope**;
  revocations, one permission taken from one person with the reason why.
* **Row scopes** - declared in code on a `ScopedQuerySet`, or built from
  rules in the admin site; `visible_to(user, action)` reads them in a fixed
  number of queries.
* **Protected fields** - read with one permission and written with another,
  in code or in the admin site, left out of every serializer, form, template,
  admin page and rule.
* **Actions** - status actions that alone write their values; actions found
  in views, viewsets and admin actions, their permissions made on `migrate`.
* **Policies** - `BasePolicy` for the rules no permission can say, and
  `ModelPolicy` for every other model.
* **Django views and DRF** - `PolicyRequiredMixin`, `ScopedQuerySetMixin`,
  `ProtectedFieldsViewMixin`, `policy_required`; `ModelPolicyPermission`,
  `PolicyPermission`, `ScopedModelViewSet`, writes refused field by field.
* **The admin site** - every `ModelAdmin` asking the policies, and the access
  pages: overview, bundles as a grid, people, permissions, the rule builder,
  protected fields, actions; right to left in Persian.
* **The safety rules** - nobody gives themselves more, gives what they do not
  hold, or leaves nobody able to manage access.
* **Access as code** - the `ACCESS` file and `clearance_sync`, with
  `--dry-run`, `--check` and `SYNC_ON_MIGRATE`.
* **`clearance.roles`** - roles with starting bundles and a ceiling.
* **`clearance.translations`** - names of permissions, bundles and roles in
  every language.
* **Checking** - system checks at start-up, and `clearance_check` for what
  only the database can tell.
* **English and Persian** throughout; Python 3.11 to 3.14, Django 5.2, 6.0
  and 6.1, DRF 3.16 and later.
