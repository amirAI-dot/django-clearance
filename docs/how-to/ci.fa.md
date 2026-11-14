# بررسی دسترسی در CI

سه دستور، که هر کدام به دلیل خودش build را ناموفق می‌کند:

```bash
python manage.py check                      # what cannot work, by the code
python manage.py clearance_sync --check     # the database differs from the ACCESS file
python manage.py clearance_check            # the database gives no access it was made to give
```

`check` موقع بالا آمدن چیزی را که نمی‌تواند کار کند رد می‌کند. `clearance_sync --check`
وقتی پایگاه داده با فایل `ACCESS` فرق دارد ناموفق می‌شود، و همه‌ی تفاوت‌ها را فهرست
می‌کند. `clearance_check` روی دامنه‌ی قانونی، اکشن وضعیت یا مجوزی که حالا به هیچ
چیزی نمی‌رسد ناموفق می‌شود، و هشدارها را بدون ناموفق شدن فهرست می‌کند.

## در GitHub Actions

```yaml
- run: python manage.py migrate
- run: python manage.py check
- run: python manage.py clearance_sync --check
- run: python manage.py clearance_check
```

`--check` و `clearance_check` پایگاه داده را می‌خوانند، پس روی یکی اجرا می‌شوند -
پایگاه داده‌ی تازه و مایگریت‌شده می‌گوید فایل اعمال می‌شود یا نه؛ نسخه‌ای از
production، می‌گوید production با آن یکی است یا نه.

## پیش از استقرار

```bash
python manage.py clearance_sync --dry-run
```

آنچه sync این استقرار تغییر خواهد داد را بدون نوشتن چیزی فهرست می‌کند - همان
بازبینی‌ای که یک تغییر در دسترسی، پیش از رسیدن به افراد، لازم دارد.
