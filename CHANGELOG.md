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

* **A scope holds for what is written.** A row created outside the scope
  `create` was given in, or edited out of the rows the person reaches, is
  refused and the write undone - in Django's views, DRF, and the admin site.
  `clearance.writes.require_within_scope` asks the same in a view that saves
  by hand. **Changed:** a grant of `create` with no scope now reaches the
  model's `default_scope`, as every other grant does - so no rows on a
  `ScopedQuerySet` that names none. Give `create` a scope.
* **An inline and the editable list change only the rows the person may
  edit**, and an inline deletes only those they may delete. Before, every
  row they could view was theirs to change there.
* **An admin action naming Django's `permissions=`** runs over the rows
  those permissions reach, not every row the person can see.

* **The safety rules hold round four more ways.** Each was open to somebody
  managing access who held nothing of what they changed:
  * changing the rows of a rule scope needs every permission granted in it,
    on every row;
  * giving back a permission that was taken away needs holding it, with the
    scopes the person's bundles give it in;
  * letting a status action write from more values is the superuser's and
    the `ACCESS` file's - **changed:** somebody not holding it could;
  * giving a person under a ceiling a second role that widens or lifts it
    needs `role_ceiling_edit`.
* **A bundle a person starts with by their role is one they hold**: they do
  not change it.

* **A protected field is not learnt another way.** Without its view
  permission it was still read, or its value narrowed down, through:
  * a filter typed into the admin site's address bar (`?price__gte=`), and
    the date hierarchy - both refused now;
  * a serializer nested in a protected one, written out or made by `depth`;
  * DRF's `SearchFilter` and `OrderingFilter` naming it, on a view with
    `ProtectedSerializerMixin` (`ScopedModelViewSet` has it);
  * a proxy of its model, or a model inheriting it from a parent with its
    own table - it has the one pair of permissions on all of them.
* **A value is refused under whatever name it is sent**: a serializer field
  with `source='status'` could write a value a status action claims, and a
  relation could be written under its column's name (`officer_id`).
* **A form in the admin site offers only the related rows the person may
  view**, and the one the row holds already. **Changed:** choosing a related
  row there needs `view` on its model.

* **`visible()` asks the queryset.** A view, the admin site and a policy
  called `visible()`, which never asked a `ScopedQuerySet` its own
  `visible_to` - so `SignedInReadQuerySet` showed a view nothing, and an
  override that narrowed was ignored. They get the queryset's answer now.
* **A scope answering with a queryset keeps the rows it was asked about.**
  Alone, it replaced the queryset, and whatever the view had filtered by -
  a tenant, say - was gone.
* **E007 refuses a backend built on `ModelBackend`**, not that one name
  only: listed before the library's, it handed back every revocation.
* **`with_perm` answers as `has_perm` does** - without whoever a permission
  was taken from or whose ceiling stops it, with whoever starts with it.
* **The pages answer rather than fail.** A bundle's key that is no number
  is a 404; a name longer than its column is refused, saying so - SQLite
  kept it whole and PostgreSQL answered with a server error.
* **A rule comparing with `None` is refused when saved**: it was kept as
  `''`, and reached nothing from then on. `is_empty` says it.
* **Fewer queries.** The overview and the actions page read the database a
  fixed number of times (about 90 before, and one more for each bundle; 19
  now), and saving a bundle no longer reads it once for each permission.

* **A refusal is said in the reader's language.** What the safety rules
  refuse, and what is wrong with a rule, a status action, a protected field
  or a name, was said in English whatever the language of the page. Each is
  marked for translation and said in Persian; `AccessRefused.rule` still
  names the rule for code.

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
