# Introduction

django-clearance decides who may do what in a Django project - and to which
rows, and with which fields. An administrator gives the access in Django's
admin site, with no code; the code says only what the project has to say:
the permissions a model has, and the scopes its rows can be reached by.

## The problem it solves

Django's permissions answer one question: may this person change orders?
A real project asks three more, and Django leaves each to the views:

* **Which orders?** A branch manager changes their branch's orders, not every
  branch's. A customer reads their own.
* **Which fields?** A manager reads the order, but not what the shop paid.
* **Which values?** Anybody who may edit an order may correct its item - but
  only whoever may approve sets it to *approved*.

Written in the views, each answer is written again in every view, in the
API, in the admin site and in every export - and the one that is forgotten
shows every customer's orders to everybody, with nothing failing.
django-clearance answers each once, in one place, and every door asks it.

## Four layers

| layer | the question | where it is decided |
|---|---|---|
| bundles | which permissions does this person hold? | the admin site, or a file |
| row scopes | which rows does a permission reach? | the scope chosen beside each permission |
| protected fields | which fields may they read, and write? | a field's own two permissions |
| roles, optional | what can this person never hold? | a role's ceiling |

Each is usable without the next. A project can start with bundles and
scopes, and add protected fields the day it needs them.

## Denied by default

* A person holds nothing they were not given.
* A permission reaches no rows until a scope says which.
* A field marked protected is left out until a permission says otherwise.
* A view that cannot say which policy to ask is refused at start-up, not on
  the day somebody finds it.

So forgetting something refuses too much - and that is noticed at once -
rather than showing too much, which is noticed by nobody.

## Every door asks the same rules

| door | what it does |
|---|---|
| Django's views | `ScopedQuerySetMixin`, `PolicyRequiredMixin`, `ProtectedFieldsViewMixin` |
| Django REST framework | `ScopedModelViewSet`, or each part alone on any view |
| the admin site | every page of every model, with no code in a `ModelAdmin` |
| your own code | `Order.objects.visible_to(user)`, `policy.allows(user, 'edit', order)` |

## What it needs

Python 3.11 to 3.14; Django 5.2, 6.0 and 6.1; Django REST framework 3.16 and
later, optional; any database Django supports. The pages, messages and
permission names come in English and Persian.

## Where to go next

* [Installation](installation.md) - a project ready in a few lines.
* [Quickstart](quickstart.md) - one model, one bundle, and the rows it reaches.
* [The tutorial](../tutorial/index.md) - the example shop, step by step.
