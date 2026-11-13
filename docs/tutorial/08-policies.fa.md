# ۸. Policyها

همه‌ی آنچه تا این‌جا دیدیم یک مجوز و یک دامنه بود، و برای تصمیم گرفتن کدی لازم
نداشت. یکی از قانون‌های فروشگاه درباره‌ی کسی که می‌پرسد نیست، درباره‌ی خود سفارش
است: هیچ کس سفارش را بعد از تحویل ویرایش نمی‌کند. این یک policy است:

```python
--8<-- "example/shop/policies.py"
```

* از مدلی که policy ندارد از طریق `ModelPolicy` پرسیده می‌شود: مجوزش، در
  دامنه‌اش. policy فقط برای قانونی نوشته می‌شود که هیچ مجوزی نمی‌تواند بگوید.
* هر hook یک `can_<action>` است. `has_within_scope` همان مجوز و دامنه است - چیزی
  که مدل بدون policy جواب می‌داد - و hook قانون خودش را بعد از آن اضافه می‌کند.
* `obj=None` پرسشی است که از یک فهرست، قبل از هر ردیفی، پرسیده می‌شود: «اصلاً
  می‌توانند سفارش‌ها را ویرایش کنند؟»

آن را جایی ثبت کنید که موقع بالا آمدن پروژه import شود - فروشگاه آن را در
`ready()` اپ خودش import می‌کند:

```python
--8<-- "example/shop/apps.py"
```

## پرسیدن از آن

همه‌ی درها از policy می‌پرسند - پنل ادمین، viewهای Django و API - و یک پروژه هم
می‌تواند:

```python
from shop.policies import order_access

order_access.policy.allows(user, 'edit', order)
order_access.policy.authorize(user, 'edit', order)    # PermissionDenied if not
```

`south_manager` مجوز `order_edit` را در شعبه‌ی خودش دارد، و فرش مال South است -
اما تحویل شده، پس در هیچ دری نمی‌تواند آن را ویرایش کند.
