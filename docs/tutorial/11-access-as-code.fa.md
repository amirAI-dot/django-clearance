# ۱۱. دسترسی به صورت کد

بسته‌ها و نقش‌هایی که یک پروژه همیشه دارد می‌توانند در یک فایل باشند، که مثل کد
بازبینی می‌شود و روی همه‌ی سیستم‌ها یکی است. فایل فروشگاه:

```python
--8<-- "example/config/access.py"
```

تنظیمات اسم آن را می‌برند، و هر `migrate` آن را اعمال می‌کند:

```python
CLEARANCE = {'ACCESS': 'config.access.ACCESS', 'SYNC_ON_MIGRATE': True}
```

یا با دست:

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

## چه چیزی مال کیست

**فایل صاحب چیزی است که نام می‌برد، و نه بیشتر.** بسته یا نقشی که فایل نام
می‌برد در پنل ادمین فقط‌خواندنی نشان داده می‌شود، با یادداشتی که همین را
می‌گوید - صفحه‌ی نقش در [قدم ۱۰](10-roles.md) را ببینید. بسته‌ای که مدیر سیستم
می‌سازد مال خود اوست، و فایل هیچ‌وقت به آن دست نمی‌زند.

**اینکه بسته یا نقشی به چه کسی داده شود کار فایل نیست.** این در پنل ادمین
می‌ماند - یا، در فروشگاه، در `example_data`.

اکشن وضعیتِ مدلی که مجوزهای Django را نگه داشته هم در فایل می‌آید، زیر
`status_actions`:

```python
ACCESS = {
    'status_actions': {
        'shop.Payment': {'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']}},
    },
}
```

فایلی که چیزی ناممکن را نام ببرد موقع بالا آمدن پروژه رد می‌شود - مجوزی که به
شکل `app_label.codename` نوشته نشده، مدلی که نصب نیست، فیلد یا مقداری که مدلش
ندارد (E001).
