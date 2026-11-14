# تست اینکه افراد چه کاری می‌توانند بکنند

قانون‌ها را تست کنید، نه viewها را: چه کسی به کدام ردیف‌ها می‌رسد، چه کسی با یک ردیف
چه کاری می‌تواند بکند. بعد تست خود view فقط می‌پرسد که آیا می‌پرسد.

## دادن دسترسی در یک تست

دسترسی را همان‌طور بدهید که پروژه می‌دهد - با `AccessService` بدون `actor`، به عنوان
خود سیستم:

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

**بعد از دادن چیزی به یک شخص، او را دوباره بخوانید** - مثل مجوزهای خود Django، آنچه
شخص دارد بعد از یک بار خوانده شدن روی شیء کاربر نگه داشته می‌شود.

## با فایل `ACCESS`

پروژه‌ای که فایل `ACCESS` دارد، آن را در setup یک تست اعمال می‌کند، تا تست‌ها
بسته‌هایی را بررسی کنند که پروژه همراه خودش دارد:

```python
from django.core.management import call_command

call_command('clearance_sync', verbosity=0)
```

`SYNC_ON_MIGRATE` هیچ‌وقت موقع ساخته شدن پایگاه داده‌ی تست اجرا نمی‌شود.

## از راه یک view

```python
self.client.force_login(self.manager)
response = self.client.get(f'/api/orders/{south_order.pk}/')
assert response.status_code == 404      # another branch's order does not exist for them
```

## شمردن کوئری‌ها

فهرستی که برای هر ردیف یک بار از پایگاه داده بپرسد ایرادی است که یک تست می‌تواند
جلویش را بگیرد:

```python
with self.assertNumQueries(5):
    self.client.get('/api/orders/')
```

این عدد هر چند سفارش و مجوز که باشد ثابت می‌ماند - ردیف اضافه کنید و دوباره
بسنجید.
