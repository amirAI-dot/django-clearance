# The tutorial

A shop, built a layer at a time: customers place orders at one of two
branches, each branch has a manager, and an accountant reads every order with
its price. Every piece of code on these pages is read straight from the
[example project](https://github.com/amirAI-dot/django-clearance/tree/main/example),
whose tests run with the library's own - so what you read here is what runs.

## What the shop needs

| who | may |
|---|---|
| a branch manager | read, edit and approve their branch's orders - never the price |
| the accountant | read every order, with its price, and change nothing |
| a customer | read their own orders, and place new ones - never priced, never approved |
| nobody | edit an order once it is delivered |

## The steps

| | step | what it adds |
|---|---|---|
| 1 | [Running the shop](01-the-shop.md) | the example, its people and its orders |
| 2 | [Permissions](02-permissions.md) | what can be done to an order |
| 3 | [Bundles](03-bundles.md) | permissions given together, in the admin site |
| 4 | [Row scopes in code](04-row-scopes.md) | "their own orders", "their branch's orders" |
| 5 | [Rule scopes in the admin site](05-rule-scopes.md) | a scope built with no code |
| 6 | [Protected fields](06-protected-fields.md) | the price, read by whoever may |
| 7 | [Status actions](07-status-actions.md) | only whoever may approve sets *approved* |
| 8 | [Policies](08-policies.md) | the rule no permission can say |
| 9 | [Views and the API](09-views-and-the-api.md) | Django's views and DRF, asking the same rules |
| 10 | [Roles](10-roles.md) | what a customer can never hold |
| 11 | [Access as code](11-access-as-code.md) | the bundles and roles, reviewed like code |
| 12 | [Names in every language](12-names-in-every-language.md) | a bundle named in Persian |

Each step stands on the one before it, but each layer works without the next:
a project can stop after step 4 and be complete.
