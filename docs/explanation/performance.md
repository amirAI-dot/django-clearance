# What it costs

Access is asked on every request, often many times. So what it costs is
counted, and held by the tests: more rows, more grants, more bundles must
never mean more queries.

## What a person holds

What Django's own backend costs: the permissions given directly and through
groups, read once and kept on the user object. The library's additions -
what was taken away, the bundles a role starts, the ceiling - are conditions
inside those same queries, not queries of their own.

## Which rows a permission reaches

A person's grants - each permission with its scope - are read once per
request, in one query, and a model's rule scopes once per request, in one
more. Every list after that is its own query and nothing else: the scopes
become one filter on it.

| a page showing | costs, beside its own queries |
|---|---|
| one list | the grants, the rules: two queries, once |
| five lists | the same two |
| a list of a thousand rows | the same two |

## One row

Asking about one row - may they edit *this* order - is one `exists()` when the
person's scope does not reach every row; nothing when it does, or when they
are the superuser.

## Names

A page that names many permissions, bundles or roles reads every name of its
language in one query (`labels_in()`), however many it shows.

## What is not cached

Nothing is kept between requests. A grant changed in the admin site is in
force on the next request, everywhere, with no cache to clear. A process that
outlives a request reads the person again - see
[Workers and websockets](../how-to/long-lived-processes.md).

## Held by the tests

The library's own suite counts the queries of each door - the admin site's
lists, the API, the views, the access pages - with `django_assert_num_queries`,
and asks again with more rows to hold that the count does not grow.
