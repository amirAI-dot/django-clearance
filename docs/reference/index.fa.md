# مرجع

همه‌ی چیزهایی که کتابخانه دارد، فهرست‌شده. [راهنما](../guide.md) توضیح می‌دهد
بخش‌ها چطور کنار هم قرار می‌گیرند؛ این بخش برای پیدا کردن یک چیز مشخص است.

## پیکربندی

| صفحه | چه چیزی آن‌جاست |
|---|---|
| [تنظیمات](settings.md) | همه‌ی کلیدهای `CLEARANCE`، با مقدار پیش‌فرضشان |
| [فایل `ACCESS`](access-file.md) | بسته‌ها، اکشن‌های وضعیت و نقش‌ها، به صورت کد |
| [بررسی‌های سیستمی](checks.md) | همه‌ی `clearance.E0xx`ها، و آنچه هر کدام موقع بالا آمدن رد می‌کند |
| [دستورهای مدیریتی](commands.md) | `clearance_sync` و `clearance_check`، با گزینه‌هایشان |
| [سیگنال‌ها](signals.md) | هر تغییری در دسترسی، اعلام‌شده - و آنچه هر کدام همراه دارد |
| [مدل‌ها](models.md) | جدول‌هایی که کتابخانه نگه می‌دارد |
| [تگ‌های قالب](template-tags.md) | `{% load clearance %}` |

## API پایتون

از خود کد خوانده می‌شود، پس هیچ‌وقت از آن عقب نمی‌ماند. توضیح‌ها مال خود کدند، و
به انگلیسی.

| صفحه | چه چیزی آن‌جاست |
|---|---|
| [مجوزها](api/permissions.md) | `build_permissions`، `permission_for` |
| [دامنه‌های ردیف](api/querysets.md) | `ScopedQuerySet`، `OwnedQuerySet`، `SignedInReadQuerySet`، `visible` |
| [Policyها](api/policies.md) | `BasePolicy`، `ModelPolicy`، registry |
| [سرویس‌ها](api/services.md) | `AccessService` - هر تغییری در دسترسی |
| [فیلدها و مقدارها](api/fields.md) | فیلدهای محافظت‌شده، اکشن‌های وضعیت، نوشتن در دامنه |
| [viewهای Django](api/views.md) | viewهای Django و decorator |
| [Django REST framework](api/drf.md) | کلاس‌های مجوز، serializerها، viewsetها |
| [پنل ادمین](api/admin.md) | `ClearanceAdminSite` |
| [نقش‌ها](api/roles.md) | `RoleService`، resolverها، `has_role` |
| [اسم‌ها](api/names.md) | `label_of`، `labels_in`، `TranslationService` |
| [گسترش دادن](api/extending.md) | محدودیت‌هایی که یک لایه بالای بسته‌ها نصب می‌کند، و پروتکل کاربر |
