# django-clearance

کنترل دسترسی مبتنی بر نقش، سیاست (policy) و سطح ردیف برای جنگو. پیش‌فرض: رد.

[English](README.md)

مدیر سایت، در پنل ادمین Django و بدون هیچ کدی، تصمیم می‌گیرد چه کسی چه کاری
می‌تواند بکند - و روی کدام ردیف‌ها، و با کدام فیلدها:

* **بسته‌های** مجوز، که هر مجوز با یک **دامنه** داده می‌شود - «سفارش‌های شعبه‌ی
  خودشان»، «مال خودشان»، یا قانونی که در پنل ادمین ساخته شده؛
* **فیلدهای محافظت‌شده**، که با یک مجوز خوانده و با مجوزی دیگر نوشته می‌شوند؛
* **اکشن‌های وضعیت** - فقط کسی که اجازه‌ی تأیید دارد یک سفارش را *approved* می‌کند؛
* **نقش‌ها**، به صورت اختیاری، با سقفی که هیچ کس با آن نقش از آن بالاتر نمی‌رود.

همه‌ی درها همان قانون‌ها را می‌پرسند: viewها و قالب‌های Django، DRF، پنل ادمین، و
کد خودتان. هر تغییری که بگذارد کسی به خودش بیشتر بدهد رد می‌شود. صفحه‌ها، پیام‌ها
و مجوزها به انگلیسی و فارسی هستند، و به فارسی راست به چپ خوانده می‌شوند.

## در یک پروژه

```bash
pip install 'django-clearance[drf]'
```

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
    'clearance',
]

AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

```python
class OrderViewSet(ScopedModelViewSet):  # the rows, the policy, the fields - asked
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


Order.objects.visible_to(user, 'edit')  # the orders this person may edit
```

* [راهنما](docs/guide.fa.md) - همه‌ی بخش‌ها، و اینکه چطور به کارشان ببرید.
* [فروشگاه نمونه](example/README.fa.md) - پروژه‌ای که همه‌اش را به کار می‌برد، برای
  اجرا کردن.
* [سند طراحی](docs/design.fa.md) - اینکه چرا این‌طور ساخته شده.

Python 3.11 تا 3.14؛ Django 5.2، 6.0 و 6.1؛ Django REST framework 3.16 و بالاتر،
به صورت اختیاری؛ هر پایگاه داده‌ای که Django پشتیبانی می‌کند.

## کار روی پروژه

همه‌ی بررسی‌ها با [nox](https://nox.thea.codes) اجرا می‌شوند؛ همان sessionها
هم روی سیستم خودتان و هم در CI. اگر [uv](https://docs.astral.sh/uv/) نصب
باشد، هر نسخه‌ای از پایتون که نصب نیست خودکار دانلود می‌شود.

```bash
uv tool install nox
```

```bash
nox -s lint
```

```bash
nox -s types
```

```bash
nox -s tests
```

`tests` همه‌ی نسخه‌های پشتیبانی‌شده‌ی پایتون و جنگو را اجرا می‌کند؛ برای
اجرای یک ترکیب: `nox -s "tests(3.13-django6.1)"`، و `nox -l` همه را فهرست
می‌کند. `browser` صفحه‌ها را در یک مرورگر واقعی اجرا می‌کند، `messages` - با
gettext نصب‌شده - بررسی می‌کند که کاتالوگ‌ها همه‌ی رشته‌هایی را که کتابخانه علامت
می‌زند داشته باشند، و `package` فایل wheel را می‌سازد و پروژه‌ی نمونه را روی آن
اجرا می‌کند.

تست‌ها به‌طور پیش‌فرض روی SQLite اجرا می‌شوند. برای اجرا روی PostgreSQL،
مثل CI، متغیر `CLEARANCE_TEST_DATABASE=postgres` را تنظیم کنید؛ اطلاعات
اتصال از متغیرهای استاندارد `PGHOST`، `PGPORT`، `PGUSER`، `PGPASSWORD` و
`PGDATABASE` خوانده می‌شود (پیش‌فرض‌ها: `localhost`، `5432`، `postgres`،
`postgres`، `clearance`).

```bash
CLEARANCE_TEST_DATABASE=postgres nox -s tests
```

بعد از علامت زدن یک رشته، با `nox -s messages` استخراجش کنید، آنچه اضافه شده را در
`locale/fa/LC_MESSAGES/django.po` ترجمه کنید، و کامپایل کنید:

```bash
cd src/clearance && django-admin compilemessages
```

## لایسنس

BSD 3-Clause - فایل [`LICENSE`](LICENSE) را ببینید.
