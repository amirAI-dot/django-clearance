# به کار بردن در پروژه‌ای که از قبل هست

پروژه‌ای که از قبل مجوزهای Django را می‌دهد، آن‌ها را نگه می‌دارد. گروه‌های Django
همان بسته‌های کتابخانه‌اند، `user.has_perm()` و `{{ perms }}` کار می‌کنند، و لازم
نیست چیزی جابه‌جا شود.

## ۱. نصب

```bash
pip install django-clearance
```

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
    'clearance',
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']   # instead of ModelBackend
```

```bash
python manage.py migrate
python manage.py check
```

`check` هر چیزی را که نمی‌تواند کار کند نام می‌برد - `ModelBackend`ی که کنار backend
تازه مانده (E007)، viewای که نمی‌تواند بگوید از کدام policy بپرسد (E009).

## ۲. فردای نصب، چه چیزی به چه می‌رسد

| مدل | مجوزی بدون دامنه |
|---|---|
| با manager ساده - `objects = models.Manager()` | همه‌ی ردیف‌ها، همان‌طور که Django همیشه می‌داد |
| با `ScopedQuerySet` بدون `default_scope` | هیچ ردیفی، تا دامنه‌ای انتخاب شود |

پس پروژه‌ای که کتابخانه را نصب می‌کند و هیچ مدلی را تغییر نمی‌دهد تغییری نمی‌بیند:
هر گروهی همان چیزی را می‌دهد که می‌داد. دامنه، مدل به مدل اضافه می‌شود.

## ۳. یک مدل در هر بار

به queryset مدل دامنه‌هایش را بدهید:

```python
from clearance.querysets import ScopedQuerySet


class OrderQuerySet(ScopedQuerySet):
    scopes = {'branch': _("Their branch's orders")}

    def scope_branch(self, user):
        return Q(branch=user.branch_id)


class Order(models.Model):
    ...
    objects = OrderQuerySet.as_manager()
```

از آن استقرار به بعد، مجوز `shop.view_order` بدون دامنه به هیچ سفارشی نمی‌رسد.
`clearance_check` همه‌ی این مجوزها را فهرست می‌کند، تا هیچ کدام جا نماند:

```bash
python manage.py clearance_check
```

```text
warning: The bundle Branch managers holds shop.view_order with no scope, and shop.Order reaches no rows by default: choose a scope for it.
```

برای هر کدام دامنه‌ای انتخاب کنید - در پنل ادمین، یا در فایل `ACCESS`. مدلی که
رفتار قبلی‌اش باید تا آن وقت بماند، آن را نام می‌برد:

```python
class OrderQuerySet(ScopedQuerySet):
    default_scope = 'all'    # a grant with no scope reaches every row, as before
```

## ۴. پرسیدن در viewها

پنل ادمین خودش می‌پرسد. viewهای Django و DRF وقتی بپرسند که بگویند - [Viewها و
API](../tutorial/09-views-and-the-api.md) را ببینید. viewای از خود شما که ردیف
می‌خواند، آن‌ها را از راه `visible_to` بخواند:

```python
orders = Order.objects.visible_to(request.user)
```
