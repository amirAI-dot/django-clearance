# django-clearance

کنترل دسترسی مبتنی بر نقش، سیاست (policy) و سطح ردیف برای جنگو. پیش‌فرض: رد.

[English](README.md)

> در حال ساخت. اینکه قرار است چه باشد، در سند طراحی آمده است:
> [`docs/design.fa.md`](docs/design.fa.md).

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
می‌کند.

تست‌ها به‌طور پیش‌فرض روی SQLite اجرا می‌شوند. برای اجرا روی PostgreSQL،
مثل CI، متغیر `CLEARANCE_TEST_DATABASE=postgres` را تنظیم کنید؛ اطلاعات
اتصال از متغیرهای استاندارد `PGHOST`، `PGPORT`، `PGUSER`، `PGPASSWORD` و
`PGDATABASE` خوانده می‌شود (پیش‌فرض‌ها: `localhost`، `5432`، `postgres`،
`postgres`، `clearance`).

```bash
CLEARANCE_TEST_DATABASE=postgres nox -s tests
```

## لایسنس

BSD 3-Clause - فایل [`LICENSE`](LICENSE) را ببینید.
