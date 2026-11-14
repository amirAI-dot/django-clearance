# فایل `ACCESS`

بسته‌ها، اکشن‌های وضعیت و نقش‌هایی که یک پروژه همیشه دارد، به صورت کد - که مثل کد
بازبینی می‌شود، و روی همه‌ی سیستم‌ها یکی است.

```python
# config/access.py - CLEARANCE = {'ACCESS': 'config.access.ACCESS'}
ACCESS = {
    'bundles': {
        'Branch managers': {'shop.order_view': 'branch', 'shop.order_approve': 'branch'},
        'Accountants': {'shop.order_view': 'all', 'shop.order_view_price': None},
    },
    'status_actions': {                  # for a model keeping Django's permissions
        'shop.Payment': {
            'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']},
        },
    },
    'roles': {                           # with clearance.roles installed
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.order_view', 'shop.order_create'],
            'bundles': ['Customers'],
        },
    },
}
```

## `bundles`

`{name: {permission: scope}}`. مجوز به شکل `app_label.codename` است؛ دامنه کد یک
دامنه است - `all`، یک دامنه‌ی کد، یک دامنه‌ی قانونی - یا `None`، برای پیش‌فرض مدل.

## `status_actions`

`{'app_label.Model': {code: spec}}`، برای مدلی که مجوزهای Django را نگه داشته. مدلی که
مجوزهای خودش را با `build_permissions` اعلام می‌کند، اکشن‌های وضعیتش را هم همان‌جا
اعلام می‌کند.

| کلید | | |
|---|---|---|
| `field` | لازم | فیلدی با گزینه، یا بولی |
| `to` | لازم | مقدارهایی که فقط این اکشن می‌نویسد |
| `from` | اختیاری | مقدارهایی که از آن‌ها می‌نویسد؛ اگر نیاید، از هر مقداری |
| `name` | اختیاری | چیزی که پنل ادمین نشان می‌دهد؛ اگر نیاید، خود کد، خواناشده |

## `roles`

وقتی `clearance.roles` نصب باشد. `{code: spec}`:

| کلید | | |
|---|---|---|
| `name` | اختیاری | اگر نیاید، خود کد، خواناشده |
| `ceiling` | اختیاری | فهرستی از مجوزها؛ `None` برای بدون سقف؛ اگر نیاید، اجازه‌ی هیچ چیزی را نمی‌دهد، مثل نقش تازه |
| `bundles` | اختیاری | بسته‌های آغازین - تعریف‌شده در فایل، یا ساخته‌شده در پنل ادمین |

## چه چیزی مال فایل است

* **فایل صاحب چیزی است که نام می‌برد، و نه بیشتر.** یک sync آنچه فایل اضافه می‌کند
  را می‌سازد، آنچه تغییر می‌دهد را تغییر می‌دهد، و آنچه زمانی نام می‌برد و دیگر
  نمی‌برد را حذف می‌کند. بسته، نقش یا اکشن وضعیتی که در پنل ادمین ساخته شده تا وقتی
  فایل اسمش را نبرد دست نمی‌خورد؛ از آن به بعد مال فایل است.
* **آنچه مال فایل است در پنل ادمین فقط‌خواندنی است** - برای همه، ابرکاربر هم - چون
  sync بعدی آن را برمی‌گرداند.
* **اینکه بسته یا نقشی به چه کسی داده شود کار فایل نیست.** این در پنل ادمین، یا در
  کد خود پروژه، می‌ماند.

## اعمال آن

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

یا در هر `migrate`، با `SYNC_ON_MIGRATE`. یک sync قبل از نوشتن هر چیزی کامل فهرست
می‌شود، و در یک تراکنش اعمال می‌شود: syncی که کسی را برای مدیریت دسترسی باقی نگذارد
چیزی را تغییر نمی‌دهد. فایلی که خوانده نشود یا چیزی ناممکن بگوید موقع بالا آمدن رد
می‌شود (E001)؛ اینکه هر مجوز و دامنه‌ای که نام می‌برد در پایگاه داده وجود دارد یا نه،
کار `--check` است.
