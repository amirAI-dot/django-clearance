# Test what people may do

Test the rules, not the views: who reaches which rows, who may do what to
one. A view's own test then only asks that it asks.

## Giving access in a test

Give access the way the project does - `AccessService` with no actor, as the
system:

```python
from django.test import TestCase

from clearance.services import AccessService


class BranchManagersTests(TestCase):
    def setUp(self):
        self.north = Branch.objects.create(name='North')
        self.manager = Person.objects.create_user('manager', branch=self.north)

        access = AccessService(actor=None)
        bundle = access.create_bundle(
            'Branch managers', grants={'shop.order_view': 'branch'}
        )
        access.give_bundle(self.manager, bundle)
        self.manager = Person.objects.get(pk=self.manager.pk)   # read what they hold now

    def test_a_manager_reads_only_their_branchs_orders(self):
        mine = Order.objects.create(branch=self.north, ...)
        Order.objects.create(branch=Branch.objects.create(name='South'), ...)

        self.assertQuerySetEqual(Order.objects.visible_to(self.manager), [mine])
```

**Read the person again after giving them something** - like Django's own
permissions, what a person holds is kept on the user object once read.

## With an `ACCESS` file

A project with an `ACCESS` file applies it in a test's setup, so the tests
check the bundles the project ships:

```python
from django.core.management import call_command

call_command('clearance_sync', verbosity=0)
```

`SYNC_ON_MIGRATE` never runs while a test database is made.

## Through a view

```python
self.client.force_login(self.manager)
response = self.client.get(f'/api/orders/{south_order.pk}/')
assert response.status_code == 404      # another branch's order does not exist for them
```

## Counting the queries

A list that asks the database once per row is a defect a test can hold:

```python
with self.assertNumQueries(5):
    self.client.get('/api/orders/')
```

The number stays the same however many orders and grants there are - add
rows and assert it again.
