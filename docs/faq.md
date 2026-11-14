# Questions

## Does it replace Django's permissions?

No - it uses them. Permissions are Django's rows, bundles are Django's
groups, and `user.has_perm()`, `{{ perms }}` and the admin site keep working.
The library adds what Django's permissions cannot say: which rows, which
fields, which values.

## How is it different from django-guardian or django-rules?

django-guardian gives a permission on one object, stored row by row: good for
"Ana may edit this document", costly for "managers edit their branch's
orders", which is a rule, not a list of rows. django-rules decides in code,
with predicates. This library decides by **scopes** - a rule about rows, in
code or built in the admin site - so a permission reaches thousands of rows
with no row stored per person, and an administrator changes who reaches what
with no deployment.

## Do I need Django REST framework?

No. `pip install django-clearance` works with Django's views, templates and
admin site. `[drf]` adds DRF beside it, for a project with an API.

## Do I need the admin site?

No. Without `ClearanceAdminConfig`, there are no access pages; access is given
in code, with `AccessService`, or in an `ACCESS` file. Everything else works.

## Why does a new grant reach no rows?

Because the model's queryset is a `ScopedQuerySet` and the grant was given
with no scope: a permission reaches no rows until a scope says which.
Choose one beside the permission - `all` for every row - or give the model a
`default_scope`. `clearance_check` lists every such grant.

## Why is a person refused right after I gave them a bundle?

What a person holds is read once and kept on the user object, as Django keeps
permissions. A user object read before the change still holds what it held.
On the next request it is read again; in a test, a shell or a worker, read
the user again, or call `forget_grants(user)`.

## Why can't I change my own access?

Nobody does - the superuser neither. Somebody who manages access could
otherwise give themselves anything. Another person who manages access makes
the change.

## Why can't the superuser change a bundle in the admin site?

The `ACCESS` file declares it: it is changed in the file, and the next sync
puts it in force. Changed in the admin site, the sync would put it back.

## Can a field be hidden from some and shown to others?

Yes - a [protected field](admin/protected-fields.md), read with one
permission and written with another, in every door.

## Does it work with a custom user model?

Yes. Every foreign key to a person is `settings.AUTH_USER_MODEL`, and the
library asks of a person only what Django's user answers.

## Which databases?

Any Django supports. The suite runs on PostgreSQL and SQLite.

## Is the admin site in Persian?

Yes - the library's pages, messages and permission names come in English and
Persian, right to left in Persian. A project's own labels are translated by
its own catalogue, and names given at runtime - a bundle, a role - by
`clearance.translations`.
