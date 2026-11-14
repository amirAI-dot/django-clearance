# پنل ادمین خود پروژه

پروژه‌ای که پنل ادمین خودش را دارد - یک عنوان، یک صفحه‌ی اضافه - از پنل کتابخانه
ارث می‌برد. پنل ادمینی که مال کتابخانه نباشد موقع بالا آمدن پروژه رد می‌شود (E016):
صفحه‌هایش از policyها نمی‌پرسیدند، و همه‌ی فیلدهای محافظت‌شده را نشان می‌دادند.

## پنل

```python
# config/admin.py
from clearance.admin.sites import ClearanceAdminSite


class ShopAdminSite(ClearanceAdminSite):
    site_header = 'The shop'
```

## اپی که آن را پیش‌فرض می‌کند

```python
# config/apps.py
from clearance.admin.apps import ClearanceAdminConfig


class ShopAdminConfig(ClearanceAdminConfig):
    default_site = 'config.admin.ShopAdminSite'
```

```python
INSTALLED_APPS = [
    'config.apps.ShopAdminConfig',   # instead of 'clearance.admin.apps.ClearanceAdminConfig'
    ...
]
```

بعد `admin.site`، و هر `@admin.register`، پنل خود پروژه است، با همه‌ی قانون‌ها و
صفحه‌های دسترسی.

## صفحه‌های خود پروژه

کلاس‌های `ModelAdmin` پروژه چیزی لازم ندارند: پنل قانون‌ها را به هر کدام می‌دهد.
صفحه‌ای کنار صفحه‌های دسترسی یک `PageSet` است، که یک بار اضافه می‌شود:

```python
ShopAdminSite.add_pages(ReportPages)
```
