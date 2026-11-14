# Denied by default

Access control fails in two directions, and they are not equally visible.

**Refusing too much** is seen at once. The person who was refused says so -
the same day, usually within the hour - and it is fixed.

**Showing too much** is seen by nobody. The customer who reads another
customer's orders does not complain; the manager who sees the price did not
know they should not. Nothing fails, nothing is logged, and it is found -
if it is found - by somebody looking for it.

So every gap the library can leave is made to fall on the side that is seen:

| a gap | is |
|---|---|
| a person given nothing | holds nothing |
| a permission given with no scope | reaches no rows, unless the model chose a default |
| a rule scope whose field is gone | reaches no rows, not every row |
| a field marked protected | left out, until a permission gives it |
| an action found in the code | held by nobody, until given |
| a role's ceiling | stops what any bundle gives |
| a view that cannot say which policy to ask | refused at start-up |
| an admin site that is not the library's | refused at start-up |
| somebody signed out, or switched off | holds nothing, whatever backend is installed |

## Why at start-up

A view that cannot ask a policy could be refused when it is called - and it
would be found the day somebody calls it, perhaps the day it ships. Refused
when the project starts, it is found by whoever starts it: the developer,
before anybody else. Django's system checks are that moment, and every
check the library adds is one of them.

## What it asks of a project

A little more saying. A model that wants every grant to reach every row says
`default_scope = 'all'`; a view that holds no record names the permission it
needs; reference data everybody reads says so with `SignedInReadQuerySet`.
Each is one line, written once, where the decision is made - rather than a
leak found where it was not.
