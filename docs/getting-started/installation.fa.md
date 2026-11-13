# نصب

## ۱. نصب بسته

```bash
pip install django-clearance            # with Django's views and admin site
pip install 'django-clearance[drf]'     # and Django REST framework
```

`[drf]` یک *extra* است: همان بسته، که Django REST framework هم کنارش نصب
می‌شود. پروژه‌ای که API ندارد آن را نمی‌نویسد.

## ۲. اضافه کردن به تنظیمات

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'clearance',
    'clearance.roles',          # optional: roles and ceilings
    'clearance.translations',   # optional: names in every language
    # ... your own apps
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']
```

سه نکته:

* **اپ ادمین جای اپ Django را می‌گیرد.** `ClearanceAdminConfig` همان پنل ادمین
  Django است، با صفحه‌های دسترسی، و هر صفحه از قانون‌ها می‌پرسد. کلاس‌های
  `ModelAdmin` شما همان‌طور که هستند می‌مانند. این اپ اختیاری است: بدون آن
  صفحه‌های دسترسی وجود ندارند، و چیز دیگری عوض نمی‌شود.
* **backend جای `ModelBackend` را می‌گیرد.** بسته‌های یک شخص، مجوزهایی که مستقیم
  به خودش داده شده و آنچه از او گرفته شده را می‌خواند. نگه داشتن `ModelBackend`
  کنار آن هر مجوزِ گرفته‌شده را پس می‌داد، پس پروژه با آن بالا نمی‌آید.
* **اپ‌های اختیاری بعد از `'clearance'` می‌آیند.**

## ۳. با Django REST framework

```python
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

بعد از آن هر view در API از policy مدل خودش می‌پرسد. viewای که نه مدل دارد و نه
policyای نام می‌برد، موقع بالا آمدن پروژه رد می‌شود - [آموزش](../tutorial/09-views-and-the-api.md) را ببینید.

## ۴. مایگریت

```bash
python manage.py migrate
```

## ۵. بررسی

```bash
python manage.py check              # what start-up can tell
python manage.py clearance_check    # what only the database can tell
```

بررسی‌های سیستمی Django موقع بالا آمدن پروژه چیزی را که نمی‌تواند کار کند رد
می‌کنند - backendی که نیست یا دو بار آمده، اپ اختیاری‌ای که جایش درست نیست،
viewای که نمی‌تواند از policy بپرسد:

| بررسی | چه چیزی اشتباه است |
|---|---|
| `clearance.E006` | `ClearanceBackend` در `AUTHENTICATION_BACKENDS` نیست |
| `clearance.E007` | `ModelBackend` کنار آن است |
| `clearance.E008` | یک اپ اختیاری بدون `'clearance'`، یا قبل از آن، نصب شده |
| `clearance.E009` | viewای که policy از آن محافظت می‌کند نمی‌تواند از آن بپرسد |
| `clearance.E016` | پنل ادمین، پنل کتابخانه نیست |

فهرست کامل در [طراحی](../design.md) است.

## قدم بعدی

[شروع سریع](quickstart.md) در چند خط به یک شخص دسترسی به ردیف‌های خودش را
می‌دهد.
