# مدل‌ها

جدول‌هایی که کتابخانه کنار جدول‌های خود Django نگه می‌دارد. بسته همان `Group` در
Django است، و مجوز همان `Permission` - کتابخانه چیزی را اضافه می‌کند که آن‌ها
نمی‌توانند نگه دارند. هر کلید خارجی به یک شخص `settings.AUTH_USER_MODEL` است، و هیچ
چیزی به صورت JSON ذخیره نمی‌شود: هر مقدار یک ردیف جداست.

هر تغییر از طریق سرویس‌ها و زیر قانون‌های ایمنی انجام می‌شود. نوشتن این جدول‌ها با
دست همه‌ی قانون‌ها را دور می‌زند.

## `clearance`

| مدل | نگه می‌دارد |
|---|---|
| `ScopeGrant` | `group` یا `user` - دقیقاً یکی - `permission`، `scope`: دامنه‌ای که یک مجوز در آن داده شده |
| `PermissionRevocation` | `user`، `permission`، `revoked_by`، `reason`، `revoked_at`: مجوزی که از یک نفر گرفته شده |
| `ScopeRule` | `content_type`، `code`، `name`، `match` - همه یا هر کدام: یک دامنه‌ی قانونی |
| `ScopeCondition` | `rule`، `position`، `field`، `operator`، `source` - یک ثابت، یک فهرست، مال شخص، هیچ - `person`: یک شرط از یک قانون |
| `ScopeConditionValue` | `condition`، `position`، `value`: یک ثابت، به صورت متن |
| `ProtectedField` | `content_type`، `field`: فیلدی که در پنل ادمین محافظت شده، با دو مجوزی که ساخت |
| `StatusAction` | `content_type`، `code`، `name`، `field`: اکشن وضعیتی که در پنل ادمین ساخته شده، با مجوزش |
| `StatusActionValue` | `action`، `end` - به یا از - `position`، `value` |
| `Declared` | آنچه فایل `ACCESS` صاحب آن است - یک بسته، یک نقش، یک اکشن وضعیت - تا sync بداند چه چیزی را می‌تواند حذف کند، و پنل ادمین آن را فقط‌خواندنی نشان دهد |
| `Access` | بدون جدول: مجوزهای خود کتابخانه را دارد - `permission_view`، `_create`، `_edit`، `_delete` و `role_ceiling_edit` |

## `clearance.roles`

| مدل | نگه می‌دارد |
|---|---|
| `Role` | `code`، `name`، `limited` |
| `RoleAssignment` | `user`، `role`، `assigned_by`، `assigned_at` |
| `RoleCeiling` | `role`، `permission`: مجوزی که یک نقش محدود اجازه می‌دهد |
| `RoleBundle` | `role`، `group`: یک بسته‌ی آغازین |

## `clearance.translations`

| مدل | نگه می‌دارد |
|---|---|
| `Translation` | `content_type`، `object_pk`، `language`، `name`، `description` - برای یک مجوز، یک بسته یا یک نقش |
