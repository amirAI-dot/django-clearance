# تنظیمات

هر چیزی که کتابخانه می‌خواند زیر یک تنظیم است، `CLEARANCE`، و پروژه به هیچ کدام
نیازی ندارد: همه‌ی کلیدها مقدار پیش‌فرض دارند.

```python
CLEARANCE = {
    'ACCESS': 'config.access.ACCESS',
    'SYNC_ON_MIGRATE': True,
}
```

کلیدی که کتابخانه نمی‌شناسد موقع بالا آمدن پروژه رد می‌شود (E011)، نه اینکه نادیده
گرفته شود: `SYNC_ON_MIGRAT` غلط‌املایی که بی‌صدا نادیده گرفته شود یعنی سیستمی که
دسترسی‌اش هیچ‌وقت عوض نمی‌شود، و هیچ کس نمی‌فهمد چرا.

| کلید | پیش‌فرض | چیست |
|---|---|---|
| `ACCESS` | `None` | مسیر نقطه‌دار [فایل `ACCESS`](access-file.md) - بسته‌ها، اکشن‌های وضعیت و نقش‌ها به صورت کد |
| `SYNC_ON_MIGRATE` | `False` | اعمال فایل `ACCESS` یک بار در پایان هر `migrate` رو به جلو |
| `RULE_DEPTH` | `3` | اینکه فیلد یک دامنه‌ی قانونی از چند رابطه می‌تواند عبور کند - عددی صحیح از ۱ |
| `PERSON_FIELDS` | `()` | فیلدهایی از مدل کاربر که دامنه‌های کد پروژه می‌خوانند - روی حساب خود شخص قفل‌اند |
| `CASCADE_UNASKED_APPS` | `()` | اپ‌هایی که یک حذف ردیف‌هایشان را بدون پرسیدن `delete` آن‌ها همراه خودش می‌برد |
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AssignmentResolver'` | با `clearance.roles`: جایی که نقش‌های یک شخص از آن خوانده می‌شود |
| `ROLE_ATTRIBUTE` | `'role'` | فیلدی از مدل کاربر که `AttributeResolver` کد نقش را از آن می‌خواند |

## `PERSON_FIELDS`

دامنه‌ی قانونی‌ای که فیلدی از شخص را می‌خواند - «شعبه‌ی شخص» - برای کتابخانه
شناخته‌شده است، و هیچ کس آن فیلد را روی حساب خودش نمی‌نویسد: یعنی تغییر دسترسی خودش.
دامنه‌ی کد برای کتابخانه شناخته‌شده نیست، پس پروژه فیلدهایی را که دامنه‌های کدش
می‌خوانند نام می‌برد:

```python
CLEARANCE = {'PERSON_FIELDS': ['branch']}
```

## `CASCADE_UNASKED_APPS`

حذف یک ردیف، برای هر ردیفی که cascade همراهش می‌برد، می‌پرسد آیا شخص اجازه‌ی حذف
آن را هم دارد. اپی که برای هر حساب یک توکن یا یک نشانی نگه می‌دارد، و `delete` آن به
هیچ کس داده نمی‌شود، هر حسابی را غیرقابل حذف می‌کرد:

```python
CLEARANCE = {'CASCADE_UNASKED_APPS': ['authtoken']}
```

از مدلی که کتابخانه از آن محافظت می‌کند - مدلی با دامنه، یا مجوزهای اعلام‌شده -
به هر حال پرسیده می‌شود.

## تنظیمات خود Django

| تنظیم | آنچه کتابخانه لازم دارد |
|---|---|
| `INSTALLED_APPS` | `'clearance.admin.apps.ClearanceAdminConfig'` به جای `'django.contrib.admin'`؛ `'clearance'`، و بعد `'clearance.roles'` و `'clearance.translations'` اختیاری |
| `AUTHENTICATION_BACKENDS` | `'clearance.backends.ClearanceBackend'`، و نه `ModelBackend` کنار آن |
| `REST_FRAMEWORK` | با DRF، `'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission']` |
| `LANGUAGES` | با `clearance.translations`، زبان‌هایی که اسم در آن‌ها داده می‌شود |
