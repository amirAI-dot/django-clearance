# ۹. Viewها و API

پنل ادمین بدون کد از قانون‌ها می‌پرسد. viewهای Django و DRF از طریق چند کلاس
می‌پرسند، و serializer، فرم و قالب چیزی درباره‌ی دسترسی نمی‌دانند.

## viewهای Django

```python
--8<-- "example/shop/views.py"
```

* `ScopedQuerySetMixin` کوئری را به ردیف‌هایی که شخص به آن‌ها می‌رسد محدود می‌کند.
* `PolicyRequiredMixin` از policy می‌پرسد. اکشن از خود view خوانده می‌شود -
  `ListView` یعنی `list`، `UpdateView` یعنی `edit` - یا با `policy_action` نام
  برده می‌شود.
* `ProtectedFieldsViewMixin` فرم را برای شخص می‌سازد، و `readable_fields` را به
  قالب می‌دهد:

```django
{% if 'price' in readable_fields %}<td>{{ order.price }}</td>{% endif %}
```

## API

```python
--8<-- "example/shop/api.py"
```

`ScopedModelViewSet` ردیف‌ها را محدود می‌کند، برای هر اکشن از policy مدل می‌پرسد،
و فیلدهایی را که شخص اجازه‌ی خواندنشان را ندارد کنار می‌گذارد. نوشتنی که اسم
فیلدی را بیاورد که نمی‌تواند بنویسد - یا مقدار وضعیتی که نمی‌تواند بگذارد - یک
400 است که اسم فیلد را می‌برد.

`print_invoice` اکشنی است که در کد پیدا می‌شود: `migrate` مجوز آن،
`shop.order_print_invoice`، را می‌سازد، و فقط کسی که آن را دارد می‌تواند صدایش
بزند.

## viewای که هیچ رکوردی ندارد

وقتی `ModelPolicyPermission` پیش‌فرض باشد، viewای که نه مدل دارد و نه policy،
موقع بالا آمدن پروژه رد می‌شود (E009) - از جمله صفحه‌ی اصلی router خود DRF.
فروشگاه مجوزی را که لازم دارد به آن می‌دهد:

```python
--8<-- "example/shop/urls.py"
```

## امتحان کنید

با `alice` وارد شوید و به `/api/orders/` بفرستید:

```json
{"branch": 1, "item": "Clock", "price": "1.00"}
```

جواب یک 400 است که اسم `price` را می‌برد: مشتری می‌تواند سفارش ثبت کند، و هیچ‌وقت
قیمتش را تعیین نمی‌کند.
