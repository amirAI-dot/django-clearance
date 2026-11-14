# The safety rules

The admin site manages everything, so whoever may manage access must not be
able to give themselves everything. Every page writes through
`AccessService`, as code does, and every page refuses the same things - with
a message saying which rule.

| refused | why |
|---|---|
| a change to your own access - your bundles, grants, what was taken from you, your roles, a bundle you hold, or one you start with by your role | somebody else who manages access does it, or the superuser |
| giving a permission you do not hold - in a bundle, by giving a bundle, or one by one | or anybody could give themselves anything through a colleague |
| giving it with a wider scope than you hold it with, unless you hold it with *all* | the same, row by row |
| a change after which nobody but the superuser could manage access | the platform would be left with nobody to run it |
| changing the rows of a rule scope your own grants are in, or without every permission granted in it | it widens your own access, or a colleague's |
| unprotecting a field you do not hold both permissions of | it gives you a field you were never given |
| releasing a status action's value, or deleting it, without holding it on every row; letting one write from more values | it gives whoever holds it more |
| lifting a role's ceiling, without `role_ceiling_edit` | it gives everybody with the role more |
| changing what the `ACCESS` file owns - the superuser too | it would come back on the next sync |
| changing or deleting an account that holds more than you | setting its password, or its e-mail address, is signing in as it |

## What a refusal looks like

The page is shown again, nothing is saved, and the message names the rule:

```text
You cannot give a permission you do not hold: shop.order_view_price.
```

```text
Nobody changes their own access.
```

```text
After this nobody but the superuser could manage access. Give somebody else permission_edit first.
```

In a Persian admin site, the same messages read in Persian.

## The superuser

The superuser holds every permission, so no rule about holding stops them.
Two still do: nobody changes their own access - the superuser neither - and
what the `ACCESS` file owns is changed in the file. Everybody else, however
much they manage, is held by every rule above. Every change is a signal,
sent once it commits, for a project that keeps a trail of who changed what.
