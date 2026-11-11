# django-clearance - طراحی

> **وضعیت: ویرایش سوم، تأییدشده.** ویرایش دوم ترتیب را تعیین کرد - اول
> بسته‌های دسترسی، در آخر نقش‌ها - و صاحب پروژه آن را تأیید کرد. این ویرایش
> چیزهایی را اضافه می‌کند که باعث می‌شوند کتابخانه از همان لحظه‌ی نصب کار کند،
> و پنل ادمین را جایی می‌کند که مدیر سایت هر کاری را که کتابخانه می‌تواند، آنجا
> انجام دهد: یک حالت **پیش‌فرض** که برای هیچ مدلی کد نمی‌خواهد، یک راه
> **سفارشی** برای مدل‌هایی که بیشتر لازم دارند، اکشن‌هایی که مدیر سایت بدون کد
> می‌سازد، scope ردیف و فیلدهای محافظت‌شده‌ای که در پنل ادمین ساخته می‌شوند،
> نقش‌هایی که در دیتابیس نگه داشته می‌شوند، و قواعد ایمنی که نمی‌گذارند پنل
> ادمین همه چیز را به کسی بدهد. مرحله‌های ۰ تا ۳ روی ویرایش اول ساخته شده‌اند؛
> بخش ۲۲ می‌گوید چه چیزی در آن‌ها عوض می‌شود.
>
> انگلیسی: [`design.md`](design.md). این سند ترجمه‌ی آن است و هر دو با هم
> به‌روز می‌شوند.

**django-clearance** - کنترل دسترسی مبتنی بر نقش، سیاست (policy) و سطح ردیف
برای جنگو. پیش‌فرض: رد.

## در یک پاراگراف

نصبش کنید، `migrate` را بزنید، پنل ادمین را باز کنید. هر مدل از قبل چهار مجوزش
را دارد - جنگو آن‌ها را می‌سازد - و هر اکشنی که کد ارائه می‌دهد مجوز خودش را
دارد که خودکار پیدا شده. مدیر سایت از مجوزها **بسته** می‌سازد و به آدم‌ها
می‌دهد؛ کنار هر مجوز **ردیف‌هایی** را که به آن‌ها می‌رسد انتخاب می‌کند؛
**فیلدهایی** را که مجوز جدا لازم دارند علامت می‌زند؛ **اکشن‌هایی** می‌سازد که
یک وضعیت را عوض می‌کنند، بدون کد؛ و وقتی پروژه انواع مختلف آدم دارد، **نقش‌هایی**
می‌سازد با یک **سقف** که هیچ بسته‌ای از آن رد نمی‌شود. برنامه‌نویس فقط برای
چیزی کد می‌نویسد که هیچ مدیری نمی‌تواند: scopeی که برای سازنده‌ی قانون خیلی
پیچیده است، قانونی در policy که هیچ مجوزی نمی‌تواند بگوید، رفتاری که یک ویو
لازم دارد.

## چهار لایه

| | لایه | سؤال | پیش‌فرض (بدون کد) | سفارشی (با کد) |
|---|---|---|---|---|
| ۱ | **بسته‌های دسترسی** | این شخص چه کاری می‌تواند بکند؟ | چهار مجوز خود جنگو برای هر مدل؛ اکشن‌هایی که در کد پیدا می‌شوند؛ اکشن‌های وضعیت که در پنل ادمین ساخته می‌شوند | `build_permissions` برای اسم‌های دیگر؛ یک policy برای قانون‌ها |
| ۲ | **scope ردیف** | روی کدام ردیف‌ها؟ | scopeهایی که در پنل ادمین از قانون‌ها ساخته می‌شوند | متدهای `scope_<name>` در یک `ScopedQuerySet` |
| ۳ | **فیلدهای محافظت‌شده** | کدام فیلدهای یک ردیف؟ | فیلدهایی که در پنل ادمین علامت می‌خورند | `protected_fields=(...)` در `build_permissions` |
| ۴ | **نقش‌ها** (اختیاری) | این نوع آدم چه کاری را هرگز نباید بکند؟ | نقش‌ها، سقفشان و بسته‌های اولیه‌شان، ساخته‌شده در پنل ادمین | نقش‌ها و سقف‌هایی که از کد مقداردهی اولیه می‌شوند |

پیش‌فرض و سفارشی دو حالت کتابخانه نیستند: برای **هر مدل** انتخاب می‌شوند و
آزادانه با هم ترکیب می‌شوند. یک پروژه می‌تواند نود مدل را به پیش‌فرض بسپارد و
برای سه مدلی که لازم دارند کد بنویسد.

بالای این لایه‌ها، برای هر منبع یک **policy** هست؛ تنها جایی که هر ویو، سرویس
و دستور می‌پرسد «آیا این شخص می‌تواند این کار را روی این شیء بکند؟». مدلی که
policy مخصوص خودش را ندارد، از طریق یک policy پیش‌فرض که از روی مجوزهایش ساخته
می‌شود پرسیده می‌شود.

scope ردیف‌ها در queryset است، نه در بررسی مجوز: DRF متد `has_object_permission`
را فقط وقتی صدا می‌زند که ویو یک شیء را پیدا کرده باشد، و ویوهای generic جنگو
اصلاً چنین hookی ندارند. لیستی که فقط با بررسی مجوز محافظت شده، همه‌ی ردیف‌ها
را برمی‌گرداند - و هیچ خطایی هم نمی‌دهد، و همین است که آن را خطرناک می‌کند.

---

## ۱. اصول

1. **پیش‌فرض رد است.** هر کمبودی به یک «نه» یا یک لیست خالی ختم می‌شود، هرگز
   به نشت داده:
   * کسی که وارد نشده، یا حسابش غیرفعال است، هیچ مجوزی ندارد و به هیچ ردیفی
     نمی‌رسد - هر Backendی که نصب باشد؛
   * مجوزی که بدون scope داده شده، به هیچ ردیفی نمی‌رسد، مگر اینکه برنامه‌نویس
     مدل برایش یک scope پیش‌فرض انتخاب کرده باشد؛
   * فیلد محافظت‌شده برای کسی که مجوزش را ندارد حذف می‌شود، و مقداری که کسی
     بدون اجازه‌ی ویرایش برایش بفرستد رد می‌شود؛
   * یک اکشن - چه در کد پیدا شده باشد و چه در پنل ادمین ساخته شده باشد - تا
     وقتی به کسی داده نشده، هیچ‌کس آن را ندارد؛
   * سقف یک نقش جلوی چیزی را که یک بسته می‌داد می‌گیرد.
2. **از لحظه‌ی نصب کار می‌کند.** `migrate` مجوزهای هر مدل و هر اکشن را می‌سازد؛
   پنل ادمین آن‌ها را مدیریت می‌کند. کد برای چیزی است که مدیر سایت نمی‌تواند
   بیان کند، هرگز برای سیم‌کشی.
3. **هیچ مجوزی بی‌اثر نیست.** هر مجوزی که در پنل ادمین هست، جایی بررسی می‌شود:
   چهار مجوز جنگو توسط ویوها و پنل ادمین، اکشنی که در کد پیدا شده توسط همان
   کدی که در آن پیدا شده، و اکشن وضعیت توسط درهایی که مقدار از آن‌ها نوشته
   می‌شود. مدیر سایت نمی‌تواند مجوزی تایپ کند که هیچ چیزی بررسی‌اش نمی‌کند -
   چنین مجوزی شبیه کنترل به نظر می‌رسید و هیچ کنترلی نبود.
4. **تنظیمات اشتباه سروصدا می‌کند.** هر چیزی که موقع بالا آمدن برنامه قابل
   بررسی است یک system check جنگو است؛ چیزی که فقط دیتابیس می‌تواند بگوید،
   `clearance_check` را شکست می‌دهد.
5. **جدول‌های خود جنگو محل ذخیره‌اند.** مجوزها ردیف‌های `auth_permission`
   هستند؛ یک بسته یک `auth.Group` است؛ بسته‌های هر شخص همان `user.groups`
   است. `user.has_perm()`، `{{ perms }}` و پنل ادمین جنگو همچنان کار می‌کنند.
6. **پرسیدن ارزان است.** فهمیدن اینکه یک شخص چه مجوزهایی دارد، همان کوئری‌هایی
   را می‌زند که Backend خود جنگو می‌زند؛ scopeهایش یک کوئری در هر درخواست که یک
   بار خوانده می‌شود؛ و یک لیست scoped یک کوئری. تست‌ها این‌ها را می‌شمارند.
7. **همه‌ی لایه‌ها اختیاری‌اند** و فقط روی مدل‌ها و در پروژه‌هایی استفاده
   می‌شوند که آن‌ها را بخواهند. تنها چیز اجباری `ClearanceBackend` است، که بدون
   آن سلب‌ها و scopeها بی‌صدا هیچ اثری نداشتند.
8. **پنل ادمین هرگز راه دور زدن قانون‌ها نیست.** هر صفحه از طریق همان سرویسی
   می‌نویسد که کد استفاده می‌کند، با همان قواعد ایمنی.
9. **کد، پنل ادمین، یا هر دو.** هر کاری که مدیر سایت در پنل ادمین انجام می‌دهد،
   برنامه‌نویس می‌تواند در کد بنویسد؛ و پنل ادمین اختیاری است - بدون
   `django.contrib.admin` کتابخانه کامل کار می‌کند. چیزی که کد تعریف کرده، در
   پنل ادمین فقط‌خواندنی نشان داده می‌شود.

---

## ۲. قابلیت‌ها (نسخه‌ی 0.1)

چیزهایی که README فهرست خواهد کرد.

* **از لحظه‌ی نصب کار می‌کند.** مجوزهای دیدن، ساختن، ویرایش و حذف هر مدل را
  `migrate` می‌سازد - و مجوزهای هر مدلی که بعداً اضافه شود.
* **بسته‌های دسترسی.** برای مجموعه‌ای از مجوزها اسم بگذارید و آن را به هر کسی
  بدهید؛ هر شخص می‌تواند چندتا داشته باشد. نقش لازم نیست.
* **scope ردیف برای هر مجوز**، که در پنل ادمین از قانون‌های ساده ساخته می‌شود -
  «شعبه، شعبه‌ی خود شخص است» - یا وقتی قانونی نمی‌تواند آن را بگوید، در کد
  نوشته می‌شود.
* **فیلدهای محافظت‌شده** که در پنل ادمین یا در کد علامت می‌خورند: قیمت یک
  سفارش بدون مجوز مخصوص خودش نشان داده نمی‌شود، یا تغییر نمی‌کند - در API، در
  فرم‌ها و در پنل ادمین.
* **اکشن بدون کد.** «تأیید سفارش» در پنل ادمین به‌صورت «می‌تواند وضعیت را
  تأییدشده یا ردشده کند» ساخته می‌شود، و هر جا که وضعیت نوشته شود اعمال می‌شود.
* **اکشن‌هایی که در کد پیدا می‌شوند.** هر `@action` در DRF، هر اکشن ادمین و هر
  ویویی که اسم یک اکشن را می‌آورد، با `migrate` مجوزش را می‌گیرد، بدون نوشتن
  هیچ کد مجوزی.
* **نقش‌ها، وقتی پروژه آن‌ها را دارد**، ساخته‌شده در پنل ادمین: یک سقف برای هر
  نقش که هیچ بسته‌ای از آن رد نمی‌شود، و بسته‌هایی که نقش از اول می‌دهد.
* **قواعد ایمنی.** هیچ‌کس دسترسی خودش را تغییر نمی‌دهد؛ هیچ‌کس چیزی را که خودش
  ندارد به کسی نمی‌دهد؛ هیچ‌کس سامانه را بدون کسی که بتواند دسترسی‌ها را
  مدیریت کند رها نمی‌کند.
* **یک پنل ادمین کامل**، راست‌به‌چپ در فارسی و سازگار با حالت تاریک: بسته‌ها به
  شکل یک جدول از مدل‌ها و اکشن‌ها با یک scope کنار هر کدام، یک سازنده‌ی قانون،
  فیلدهای محافظت‌شده، اکشن‌ها، نقش‌ها و سقف‌ها، و وضعیت کامل هر شخص.
* **هر نوع ویو.** `APIView`، ویوهای generic، mixinها، ویوست‌ها، `ModelViewSet` و
  `@api_view` در DRF؛ ویوهای generic و ویوهای تابعی در جنگو.
* **دسترسی به‌صورت کد.** بسته‌ها، نقش‌ها و سقف‌ها در فایلی نوشته می‌شوند که در git
  می‌ماند و `clearance_sync` اعمالش می‌کند؛ این دستور با `--dry-run` اول هر
  تغییری را نشان می‌دهد، و با `--check` وقتی دیتابیس با فایل فرق دارد CI را
  شکست می‌دهد. چیزی که فایل تعریف کرده، در پنل ادمین فقط‌خواندنی است.
* **پنل ادمین اختیاری است.** همه چیز بدون آن هم کار می‌کند.
* **گرفتن یک مجوز از یک نفر**، از هر بسته‌ای که آن را داده باشد.
* **policy** با hookهای سطح شیء که scope ردیف را رعایت می‌کنند.
* **اسم هر مجوز، هر بسته و هر نقش به هر زبانی.**
* **signal برای هر تغییر**، برای audit مخصوص خود پروژه.
* **ترجمه‌شده و دارای type.**

---

## ۳. کل مدل در یک تصویر

```
held     = direct grants + their bundles' permissions + their roles' starting bundles' permissions
         - what was taken away from them
allowed  = held, within the ceilings of their roles            (only when roles are used)

rows     = the union of the scopes of every grant of that permission that reaches them
fields   = a protected field needs its view permission to be read, and its edit one too to be written
values   = a status action's values need that action's permission to be written
```

یعنی:

* **مجوزهای شخص** = مجوزهای مستقیم + مجوزهای بسته‌هایش + مجوزهای بسته‌های
  اولیه‌ی نقش‌هایش - چیزهایی که از او گرفته شده.
* **مجوزهای مجاز** = همان، محدود به سقف نقش‌هایش (فقط وقتی نقش استفاده شود).
* **ردیف‌ها** = اجتماع scopeهای هر مجوزی از آن نوع که به او می‌رسد.
* **فیلدها** = فیلد محافظت‌شده برای دیدن `<codename>_view_<field>` و برای
  نوشتن `_edit_` را می‌خواهد.
* **مقدارها** = مقدارهای یک اکشن وضعیت برای نوشته شدن مجوز همان اکشن را
  می‌خواهند.

superuser همه‌ی مجوزها را دارد، به همه‌ی ردیف‌ها می‌رسد، و همه‌ی فیلدها و
مقدارها را می‌خواند و می‌نویسد.

---

## ۴. ساختار بسته

```
src/clearance/
    __init__.py            empty
    apps.py                ClearanceConfig - registers the checks, finds the actions on migrate
    conf.py                reading and validating the CLEARANCE setting
    protocols.py           User - the three things the library asks of a person
    permissions.py         build_permissions; which permission an action of a model needs
    registry.py            one policy per resource, and the default policy for every other model
    policies.py            BasePolicy, ModelPolicy, SignedInReadPolicy
    models.py              ScopeGrant, PermissionRevocation, ScopeRule, ProtectedField, StatusAction
    backends.py            ClearanceBackend
    grants.py              what a person holds, and with which scopes - read once per request
    limits.py              what a layer above bundles adds: starting bundles, a ceiling
    rules.py               a ScopeRule's conditions, checked and turned into a Q
    actions.py             status actions, and writable_values()
    health.py              what only the database can say is wrong - for clearance_check
    discovery.py           the actions found in the code, and their permissions on migrate
    writes.py              refused_writes() - what a person may not write, of what they sent
    services.py            AccessService: every change, under the safety rules, with signals
    safety.py              the safety rules
    declared.py            the ACCESS file: read, compared with the database, applied
    querysets.py           ScopedQuerySet: named scopes, visible_to(user, action)
    fields.py              readable_fields(), writable_fields()
    forms.py               ProtectedFieldsFormMixin
    views.py               ScopedQuerySetMixin, PolicyRequiredMixin, ProtectedFieldsViewMixin
    decorators.py          policy_required
    labels.py              label_of()
    admin/                 'clearance.admin.apps.ClearanceAdminConfig', for 'django.contrib.admin'
        apps.py            ClearanceAdminConfig - the library's site as the default one
        sites.py           ClearanceAdminSite - every ModelAdmin given the hooks, the pages added
        options.py         the hooks: policies, rows, fields, values, actions
        views.py           PageSet, and the overview, bundles, people and permissions pages
        scopes.py          the row scopes pages and the rule builder
        protection.py      the protected fields pages
        actions.py         the actions pages
        standing.py        Standing, PermissionGrid
        discovery.py       AdminActionFinder
        checks.py          E016
    templates/, static/    the pages' templates, stylesheet and rule builder script - no build step
    checks.py              the system checks
    signals.py             every signal the library sends
    management/commands/   clearance_sync, clearance_check
    migrations/
    locale/fa/LC_MESSAGES/

    drf/                   pip install django-clearance[drf]
        permissions.py     PolicyPermission, ModelPolicyPermission - writes guarded
        viewsets.py        ScopedModelViewSet, ScopedReadOnlyViewSet, ProtectedSerializerMixin
        serializers.py     ProtectedFieldsSerializerMixin
        discovery.py       APIViewFinder - @actions and policy_action
        checks.py          E003, E009

    roles/                 INSTALLED_APPS += ['clearance.roles']
        models.py          Role, RoleAssignment, RoleBundle, RoleCeiling
        resolvers.py       RoleResolver, AssignmentResolver, AttributeResolver, roles_of(), has_role()
        limits.py          RoleLimits - installed in clearance.limits when the app starts
        services.py        RoleService
        pages.py, admin.py the roles pages, mounted beside the access pages
        checks.py          E008, E010
        declared.py        the roles section of the ACCESS file
        signals.py

    translations/          INSTALLED_APPS += ['clearance.translations']
        models.py          PermissionTranslation, BundleTranslation, RoleTranslation
        sources.py
        admin/
```

همه‌ی فایل‌های `__init__.py` خالی‌اند؛ هر چیزی از همان ماژولی import می‌شود که
تعریفش کرده. هسته هیچ چیزی از `drf`، `roles` یا `translations` import نمی‌کند.

---

## ۵. API، با یک مثال

یک فروشگاه: سفارش‌هایی که مشتری‌ها در یکی از چند شعبه ثبت می‌کنند، و کارمندهایی
که آن‌ها را مدیریت می‌کنند و فقط بعضی‌شان اجازه‌ی دیدن قیمت را دارند.

### ۵.۱ پیش‌فرض: بدون کد

```python
INSTALLED_APPS += ['clearance']

# Replaces django.contrib.auth.backends.ModelBackend - see E006 and E007.
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

# Every DRF view asks the model's policy, unless it names another.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

```python
class Order(models.Model):          # nothing about access in the model
    customer = models.ForeignKey(Customer, ...)
    branch = models.ForeignKey(Branch, ...)
    status = models.CharField(choices=Status.choices, ...)
    price = models.DecimalField(...)
```

`migrate` مجوزهای `shop.view_order`، `add_order`، `change_order` و
`delete_order` را ساخته، همان‌طور که جنگو همیشه ساخته. مدیر سایت در پنل ادمین:

1. برای سفارش‌ها یک **scope ردیف** به اسم «شعبه‌ی خودش» می‌سازد: *شعبه* -
   *برابر با* - *شعبه‌ی خود شخص*؛
2. **قیمت** را محافظت‌شده علامت می‌زند؛
3. یک **اکشن وضعیت** به اسم «تأیید» می‌سازد: *وضعیت* به *تأییدشده* یا
   *ردشده*، از *در انتظار*؛
4. یک **بسته** به اسم «مدیران شعبه» می‌سازد: دیدن و ویرایش سفارش‌ها در «شعبه‌ی
   خودش»، و «تأیید» در «شعبه‌ی خودش» - ولی نه قیمت؛
5. بسته را به آدم‌ها می‌دهد.

حالا هر لیستی از سفارش‌ها به مدیر شعبه، سفارش‌های شعبه‌ی خودش را بدون قیمت
نشان می‌دهد و اجازه می‌دهد یکی را تأیید کند - در API، در ویوهای جنگو، و در پنل
ادمین.

### ۵.۲ سفارشی: کد برای چیزی که پنل ادمین نمی‌تواند بگوید

```python
from clearance.permissions import build_permissions
from clearance.querysets import ScopedQuerySet

class OrderQuerySet(ScopedQuerySet):
    default_scope = 'all'      # optional: what a grant with no scope reaches
    scopes = {
        'own': _('Their own orders'),
        'paid_this_month': _("This month's paid orders"),
    }

    def scope_own(self, user):
        return Q(customer__user=user)

    def scope_paid_this_month(self, user):
        return Q(payments__status='paid', payments__paid_at__gte=month_start())

class Order(models.Model):
    ...
    objects = OrderQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        permissions = build_permissions('order', _('orders'), protected_fields=('price',))
```

scopeهای کد و scopeهای ساخته‌شده در پنل کنار هم ارائه می‌شوند؛ فیلدهای
محافظت‌شده‌ای که در کد تعریف شده‌اند و آن‌هایی که در پنل علامت خورده‌اند به یک
شکل اعمال می‌شوند.

### ۵.۳ یک policy، برای قانونی که هیچ مجوزی نمی‌تواند بگوید

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class OrderPolicy(BasePolicy):
    app_label = 'shop'
    codename = 'order'

    def can_edit(self, user, obj=None):
        if not super().can_edit(user, obj):
            return False
        return obj is None or obj.status != 'delivered'   # nobody edits a delivered order

order_access = registry.register(OrderPolicy)
```

مدلی که policy مخصوص خودش را ندارد، از طریق `ModelPolicy` پرسیده می‌شود، که همان
کاری را می‌کند که `BasePolicy` با مجوزهای خود آن مدل می‌کند.

### ۵.۴ هر نوع ویو

| ویو | مجوز | ردیف‌ها |
|---|---|---|
| `APIView` | `ModelPolicyPermission`، بر اساس متد HTTP | `Order.objects.visible_to(request.user, 'view')` |
| `GenericAPIView`، `generics.*` | همان | `ScopedQuerySetMixin` مقدار `queryset` را محدود می‌کند |
| `ViewSet` | بر اساس action | `visible_to` |
| `GenericViewSet` با mixinها | بر اساس action | `ScopedQuerySetMixin` |
| `ModelViewSet` | بر اساس action | `ScopedQuerySetMixin`، یا `ScopedModelViewSet` |
| تابع `@api_view` | `@permission_classes([...])` | `visible_to` |
| `ListView`، `DetailView`، `UpdateView` و بقیه در جنگو | `PolicyRequiredMixin` | `ScopedQuerySetMixin` |
| ویوی تابعی جنگو | `@policy_required(policy, action)` | `visible_to` |

```python
class OrderListCreate(ScopedQuerySetMixin, generics.ListCreateAPIView):
    queryset = Order.objects.all()          # narrowed to visible_to(user, 'view')
    serializer_class = OrderSerializer      # price left out without its permission

class OrderReport(APIView):
    def get(self, request):
        orders = Order.objects.visible_to(request.user, 'view')
        ...
```

`ScopedModelViewSet` یک `ModelViewSet` است با سه چیز اضافه، که هر کدام جداگانه
روی هر ویوی دیگر DRF هم کار می‌کند: `ScopedQuerySetMixin`،
`ModelPolicyPermission`، و `ProtectedSerializerMixin`، که به serializer ویو
`ProtectedFieldsSerializerMixin` را می‌دهد، چه برایش نوشته شده باشد چه نه.
`ScopedReadOnlyViewSet` همین است روی یک `ReadOnlyModelViewSet`.

### ۵.۵ اکشن‌هایی که در کد پیدا می‌شوند

```python
class OrderViewSet(ScopedQuerySetMixin, viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def print_invoice(self, request, pk=None):    # shop.order_print_invoice, made on migrate
        ...

class OrderPrintView(APIView):
    policy_action = 'print_invoice'                # the same permission

class OrderAdmin(admin.ModelAdmin):
    actions = ['export_excel']                     # shop.order_export_excel

@policy_required(order_access.policy, 'refund')    # shop.order_refund
def refund(request, pk):
    ...
```

### ۵.۶ بیرون از ویو

```python
Order.objects.visible_to(user, 'edit')       # the orders they may edit
readable_fields(user, Order)                 # {'id', 'customer', 'branch', 'status'}
writable_values(user, Order, 'status')       # {'pending', 'cancelled'} - not approved
order_access.policy.authorize(user, 'edit', order)
```

### ۵.۷ در کد، همان چیزی که در پنل ادمین

```python
from clearance.services import AccessService

access = AccessService(actor=request.user)

managers = access.create_bundle(
    'Branch managers',
    grants={'shop.view_order': 'branch', 'shop.change_order': 'branch'},
)
access.give_bundle(person, managers)
access.revoke(person, 'shop.change_order', reason='Under review')
```

### ۵.۸ دسترسی به‌صورت کد

```python
# config/access.py - CLEARANCE = {'ACCESS': 'config.access.ACCESS'}
ACCESS = {
    'bundles': {
        'Branch managers': {'shop.view_order': 'branch', 'shop.order_approve': 'branch'},
        'Accountants': {'shop.view_order': 'all', 'shop.view_order_price': None},
        'Customers': {'shop.view_order': 'own', 'shop.add_order': None},
    },
    'status_actions': {                  # for a model keeping Django's permissions
        'shop.Order': {
            'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
        },
    },
    'roles': {                           # with clearance.roles installed
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.view_order', 'shop.add_order'],   # None: no ceiling
            'bundles': ['Customers'],
        },
    },
}
```

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs from the file
python manage.py clearance_sync              # apply, and say what changed
```

**فایل صاحب چیزی است که نام می‌برد، و نه چیز دیگری.** یک sync چیزی را که فایل
اضافه می‌کند می‌سازد، چیزی را که تغییر می‌دهد تغییر می‌دهد، و چیزی را که یک بار نام
برده و دیگر نام نمی‌برد حذف می‌کند. بسته، نقش یا اکشن وضعیتی که در پنل ادمین ساخته
شده، تا وقتی فایل آن را نام نبرد دست نمی‌خورد - sync این را می‌گوید - و از آن به
بعد صاحبش فایل است. اینکه چه کسی یک بسته یا نقش را دارد کار فایل نیست: در پنل
ادمین می‌ماند.

یک sync قبل از نوشتن هر چیزی کامل فهرست می‌شود، و در یک transaction از طریق همان
سرویس‌هایی که پنل ادمین به کار می‌برد، به عنوان سیستم، اعمال می‌شود: syncی که بعد
از آن هیچ‌کس نتواند دسترسی‌ها را مدیریت کند، هیچ چیزی را تغییر نمی‌دهد. چیزی که
صاحبش فایل است برای هر شخصی - superuser هم - رد می‌شود، چون sync بعدی آن را
برمی‌گرداند؛ پنل ادمین آن را *تعریف‌شده در کد* نشان می‌دهد.

`bundles` و `status_actions` بخش‌های هسته‌اند؛ `clearance.roles` وقتی نصب باشد
`roles` را اضافه می‌کند. E001 موقع راه‌اندازی چیزی را بررسی می‌کند که بدون دیتابیس
می‌شود گفت - اینکه فایل خوانده می‌شود، و چیزی نمی‌گوید که نمی‌تواند باشد؛ اینکه هر
مجوز و scopeی که نام می‌برد وجود دارد، با `--check` گفته می‌شود.

---

## ۶. مجوزهای پیش‌فرض و سفارشی

مجوزهای یک مدل همان مجوزهای **پیش‌فرض** آن هستند، مگر اینکه مجوزهای خودش را
تعریف کند:

| | پیش‌فرض | سفارشی |
|---|---|---|
| تعریف‌کننده | جنگو، برای هر مدل | `build_permissions` در `Meta.permissions`، همراه `default_permissions = ()` |
| دیدن / ساختن / ویرایش / حذف | `view_order`، `add_order`، `change_order`، `delete_order` | `order_view`، `order_create`، `order_edit`، `order_delete` |
| یک فیلد | `view_order_price`، `change_order_price` | `order_view_price`، `order_edit_price` |
| یک اکشن | `order_<action>` | `order_<action>` |

`permission_for(model, action)` جواب می‌دهد که یک action از یک مدل کدام مجوز را
لازم دارد، هر کدام که باشد، و همه‌ی بخش‌های کتابخانه از آن می‌پرسند - پس هیچ
جایی اسم یک مجوز با دست نوشته نمی‌شود. مدلی که بعداً اضافه و migrate شود، فوراً
مجوزهایش را دارد، چون جنگو آن‌ها را می‌سازد.

مدلی که مجوزهای خودش را تعریف می‌کند، مجوزهای جنگو را با
`default_permissions = ()` خاموش می‌کند؛ مدلی که هر دو را نگه دارد، مجوزی ارائه
می‌دهد که هیچ چیزی بررسی‌اش نمی‌کند، و رد می‌شود (E014). صفحه‌های ادمین خود جنگو
هم از `permission_for` می‌پرسند، پس مدلی که مجوزهای سفارشی دارد، در پنل ادمین
توسط هر کسی که آن مجوزها را دارد ویرایش می‌شود، نه فقط توسط superuser.

**`migrate` قفل‌ها را می‌سازد؛ `clearance_sync` کلیدها را می‌دهد.** `migrate` هر
مجوزی را می‌سازد - مجوز یک مدل، یک فیلد، یک اکشن، چه در کد پیدا شده باشد و چه
آنجا تعریف شده باشد - همان‌طور که جنگو مجوزهای خودش را می‌سازد: فقط اضافه
می‌کند، هرگز حذف نمی‌کند، و بی‌خطر است، چون هیچ‌کس مجوز تازه را تا وقتی به او داده
نشده ندارد. دادن دسترسی - بسته‌ها، نقش‌ها و سقف‌هایی که یک فایل `ACCESS` تعریف
می‌کند - کار `clearance_sync` است، یک قدم صریح که پیش از تغییر دادن، نشان
می‌دهد چه چیزی را تغییر خواهد داد. پروژه‌ای که یک دستور می‌خواهد،
`SYNC_ON_MIGRATE` را روشن می‌کند: آن وقت sync یک بار، در پایان یک `migrate` رو
به جلو روی دیتابیس اصلی اجرا می‌شود، بعد از اینکه آخرین اپ مجوزهایش را ساخت -
هرگز موقع ساختن دیتابیس تست، و هرگز موقع یک migration رو به عقب.

دسترسی خود کتابخانه به خودش هم مجوزهای خودش را دارد:
`clearance.permission_view`، `permission_create`، `permission_edit`،
`permission_delete` و `clearance.role_ceiling_edit`. superuser آن‌ها را دارد؛
هیچ‌کس دیگری تا وقتی به او داده نشده ندارد.

---

## ۷. لایه‌ی ۱: بسته‌های دسترسی

یک **بسته** یک `Group` جنگو است. بسته‌های هر شخص همان `user.groups` است، پس هر
شخص می‌تواند چندتا داشته باشد. کتابخانه این‌ها را اضافه می‌کند: یک scope کنار
هر مجوز در یک بسته؛ سلب مجوز - گرفتن یک مجوز از یک نفر، از هر بسته‌ای که آن را
داده باشد؛ اسم به هر زبانی؛ و یک سرویس، `AccessService`، که هر صفحه و هر خط کد
از طریق آن دسترسی را تغییر می‌دهد.

`ClearanceBackend` جای `ModelBackend` را می‌گیرد. مجوزهای هر شخص را با همان
کوئری‌هایی که `ModelBackend` می‌زند حساب می‌کند - سلب‌ها و سقف‌ها داخل همان
کوئری کم می‌شوند - و cache جنگو را نگه می‌دارد.

---

## ۸. اکشن‌ها

یک مدل، علاوه بر دیدن، ساختن، ویرایش و حذف، اکشن‌هایی دارد که پروژه‌اش به آن
می‌دهد. این اکشن‌ها دو نوع‌اند، و مدیر سایت نمی‌تواند نوع سومی بسازد - مجوزی که
هیچ چیزی پشتش نیست (اصل ۳).

### ۸.۱ اکشن‌های وضعیت، ساخته‌شده در پنل ادمین

بیشتر اکشن‌ها یک مقدار را عوض می‌کنند: تأیید کردن یک سفارش وضعیتش را
*تأییدشده* می‌کند، ارسال کردنش *ارسال‌شده*، و منتشر کردن یک پست *منتشرشده*. یک
**اکشن وضعیت** دقیقاً همین را می‌گوید و هیچ کدی لازم ندارد:

| | |
|---|---|
| مدل | سفارش |
| اسم | تأیید |
| فیلد | `status` - فیلدی با choices، یا یک boolean |
| به | *تأییدشده*، *ردشده* |
| از | *در انتظار* - اختیاری |

ذخیره کردنش مجوز `shop.order_approve` را می‌سازد. کسی که آن را ندارد نمی‌تواند
آن مقدارها را بنویسد: فرم گزینه‌ها را بدون آن‌ها نشان می‌دهد و اگر باز هم یکی
فرستاده شود، رد می‌کند و اسم فیلد را می‌گوید؛ پنل ادمین هم همین‌طور،
و یک API آن‌ها را رد می‌کند و اسم فیلد و مقدار را می‌گوید. اکشن وضعیت
هم مثل هر مجوز دیگری scope می‌گیرد - «تأیید، در شعبه‌ی خودش» - و همراه با ردیف از
policy مدل پرسیده می‌شود، پس hookی مثل «هرگز وام خودش» هم برقرار می‌ماند. چند
اکشن می‌توانند یک فیلد مشترک داشته باشند، و مقداری که هیچ اکشنی ادعایش نکرده، با
همان `edit` خود ردیف نوشته می‌شود.

`از` از روی ردیف، همان‌طور که الان هست، خوانده می‌شود: ردیف تازه از مقدار پیش‌فرض
فیلد شروع می‌کند. مقداری که ردیف همین الان دارد همیشه نوشتنی است - نگه داشتنش
تغییری نیست.

اکشن وضعیتی که در پنل ادمین، از طریق `AccessService`، ساخته می‌شود رد می‌شود اگر
فیلدش choices نداشته باشد و بله/خیر هم نباشد، اگر مقداری از مقدارهای فیلد نباشد،
یا اگر کدش اکشنی باشد که مدل از قبل دارد. دو رد دیگر هم برقرار است، چون یک تغییر
می‌تواند چیزی به کسی بدهد که هیچ‌کس به او نداده:

* **آزاد کردن یک مقدار، یا حذف اکشن، داشتن آن اکشن روی همه‌ی ردیف‌ها را لازم
  دارد** - چون بعد از آن هر کسی که بتواند ردیف را ویرایش کند آن مقدار را می‌نویسد؛
* **هیچ‌کس نمی‌گذارد اکشنی که خودش دارد از مقدارهای بیشتری بنویسد** (`own_action`).

همین کار در کد - در `build_permissions`، یا برای مدلی که مجوزهای جنگو را نگه
داشته در فایل `ACCESS` - که در پنل ادمین فقط‌خواندنی نشان داده می‌شود:

```python
permissions = build_permissions(
    'order', _('orders'),
    status_actions={
        'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
        'ship': {'field': 'status', 'to': ['shipped']},
    },
)
```

### ۸.۲ اکشن‌هایی که در کد پیدا می‌شوند

اکشنی که کار تازه‌ای انجام می‌دهد - فاکتور چاپ می‌کند، خروجی اکسل می‌دهد، پولی
را برمی‌گرداند - کد لازم دارد، ولی کد مجوز لازم ندارد. یک policy اکشنی را که hook
ندارد، مثل چهار اکشن استاندارد، با مجوز و scopeاش تصمیم می‌گیرد، پس
`policy_action = 'print_invoice'` هیچ کد دیگری لازم ندارد. `migrate` (و
`clearance_sync`) همه‌شان را در URLconf پیدا می‌کند و مجوزشان را می‌سازد:

| در کد | تبدیل می‌شود به |
|---|---|
| یک `@action` در DRF روی ویوستی که از یک policy می‌پرسد | `<codename>_<action>` |
| `policy_action = '...'` روی یک `APIView` یا یک ویوی جنگو | همان |
| `@policy_required(policy, '...')` روی یک ویوی تابعی | همان |
| یک مورد در `actions` یک `ModelAdmin` که `permissions=` ندارد | همان؛ آن اکشن ادمین فقط به کسی که آن را دارد نشان داده می‌شود، و روی ردیف‌هایی اجرا می‌شود که scopeاش به آن‌ها می‌رسد |

اکشنی که پیدا شده تا وقتی به کسی داده نشده، هیچ‌کس آن را ندارد؛ پس اکشنی که
اسمش غلط نوشته شده برای همه رد می‌شود، و در پنل ادمین با همان اسم غلط دیده
می‌شود. اکشنی که policy برایش hook نوشته پیدا نمی‌شود: hook تصمیمش را می‌گیرد، و
اگر از مجوزی استفاده کند آن را همراه مدل تعریف می‌کند - مجوزی که برایش ساخته شود
مجوزی است که هیچ چیزی آن را بررسی نمی‌کند. اکشنی که دیگر در کد نیست، در پنل
ادمین «حذف‌شده» علامت می‌خورد و `clearance_check` فهرستش می‌کند.

پیدا کردن را `ActionFinder`ها انجام می‌دهند، یکی برای هر نوع کد، پس درهای DRF و
پنل ادمین مال خودشان را اضافه می‌کنند بدون اینکه چیز دیگری تغییر کند.

---

## ۹. لایه‌ی ۲: scope ردیف

### ۹.۱ scopeهایی که یک مدل ارائه می‌دهد

* **`all`** - همه‌ی ردیف‌ها - همیشه.
* **scopeهای قانونی**، ساخته‌شده در پنل ادمین (۹.۲)، برای هر مدلی.
* **scopeهای کد**، برای مدلی که با یک `ScopedQuerySet` مدیریت می‌شود: متدهای
  `scope_<code>` که در `scopes` فهرست شده‌اند، برای قانونی که هیچ سازنده‌ای
  نمی‌تواند بگوید.

مجوزی که بدون scope داده شده، به `default_scope` queryset می‌رسد؛ و اگر هیچ‌کدام
نام برده نشده باشد - حالت پیش‌فرض - به هیچ ردیفی. این انتخاب با برنامه‌نویس است،
یک بار برای هر مدل. مدلی که manager معمولی دارد querysetی ندارد که یکی را نام
ببرد، پس مجوز بدون scope روی آن به همه‌ی ردیف‌ها می‌رسد، همان‌طور که جنگو همیشه
کرده، تا وقتی برایش scopeی انتخاب شود.

### ۹.۲ سازنده‌ی قانون

یک **scope قانونی** یک اسم و چند شرط است که با *همه‌ی* یا *هر کدام از* به هم وصل
می‌شوند. هر شرط سه بخش دارد:

| بخش | می‌تواند باشد |
|---|---|
| یک فیلد | فیلدی از مدل، یا فیلدی که از طریق رابطه‌هایش به آن می‌رسیم، حداکثر `RULE_DEPTH` (سه) قدم دورتر |
| یک عملگر | برابر است، برابر نیست، یکی از این‌هاست، شامل است، خالی است، قبل از، بعد از، حداقل، حداکثر |
| یک مقدار | یک مقدار ثابت - «تهران» - یا چیزی از خود شخص: *خود شخص*، *شعبه‌ی شخص*، هر فیلدی از کاربر که به همین شکل به آن برسیم |

پس «شعبه‌ی خودش» یعنی *شعبه - برابر است - شعبه‌ی شخص*؛ «مال خودش» یعنی *مشتری،
کاربر - برابر است - خود شخص*؛ «سفارش‌های بزرگ» یعنی *قیمت - حداقل -
۱۰٬۰۰۰٬۰۰۰*.

یک قانون موقع ذخیره شدن، با مدل همان‌طور که هست بررسی می‌شود: هر فیلد باید وجود
داشته باشد، هر عملگر باید به فیلدش بخورد، و **هیچ شرطی نمی‌تواند یک فیلد
محافظت‌شده یا رمز عبور کاربر را بخواند** - فیلتری روی قیمت، به کسی که
`view_price` ندارد می‌گفت قیمت چقدر است. یک مقدار ثابت باید مقداری باشد که فیلد
بتواند نگه دارد، و اگر فیلد گزینه دارد یکی از گزینه‌هایش؛ مقداری از خود شخص باید
همان نوع چیزی را نگه دارد که فیلد نگه می‌دارد. هر مشکل، شرط به شرط، نام برده
می‌شود. قانون وقتی یک لیست خواسته شود به یک `Q` جنگو تبدیل می‌شود - هرگز SQL.
قانونی که بعد از ذخیره شدن فیلدش از بین رفته، **به هیچ ردیفی نمی‌رسد**، نه به
همه‌ی ردیف‌ها: در لاگ ثبت می‌شود، و `clearance_check` آن را فهرست می‌کند.

یک قانون و یک scope کد کنار هم ارائه می‌شوند، و ردیف‌های یک شخص اجتماع همه‌ی
scopeهایی است که به او می‌رسند. کد یک قانون اسمی مخصوص خودش است: هرگز `all`،
هرگز کد یک scope کدِ همان مدل.

قانون‌ها از طریق `AccessService` و با مجوزهای خود کتابخانه ساخته، تغییر داده و
حذف می‌شوند، و دو رد دیگر هم برقرار است:

* **هیچ‌کس ردیف‌های قانونی را که مجوزهای خودش در آن است تغییر نمی‌دهد** - دسترسی
  خودش را بازتر می‌کرد (`own_scope`)؛ تغییر اسمش تغییری در ردیف‌های کسی نیست؛
* **قانونی که هنوز در یک مجوز انتخاب شده حذف نمی‌شود** - آن مجوز بدون اینکه کسی
  تصمیمش را گرفته باشد به هیچ ردیفی نمی‌رسید. اول مجوزهایش جابه‌جا می‌شوند.

### ۹.۳ یک شخص به کدام ردیف‌ها می‌رسد

`visible(queryset, user, action='view')`، برای هر querysetی از هر مدلی -
و `Model.objects.visible_to(user, action)` روی یک `ScopedQuerySet`:

1. وارد نشده، یا غیرفعال -> هیچ ردیفی؛ superuser -> همه‌ی ردیف‌ها؛
2. شخص مجوز آن action را ندارد -> هیچ ردیفی؛
3. وگرنه scopeهای هر مجوزی از آن نوع که به او می‌رسد با OR در **یک** filter
   ترکیب می‌شوند؛ `all` آن را همه‌ی ردیف‌ها می‌کند.

مجوزهای شخص یک بار در هر درخواست، با یک کوئری، خوانده می‌شوند، و قانون‌های یک مدل
یک بار در هر درخواست، با یک کوئری دیگر؛ بعد از آن یک لیست فقط کوئری خودش را
هزینه دارد. مدلی که manager معمولی دارد بدون هیچ تغییری در کدش با قانون scope
می‌گیرد: ویو `visible` را صدا می‌زند، و `ScopedQuerySetMixin` این کار را برای هر
querysetی انجام می‌دهد.

### ۹.۴ یک شیء

وقتی شیئی به hook یک policy داده شود، hook هم مجوز را می‌خواهد **و** هم اینکه شیء
داخل scope شخص برای آن action باشد. یک ویو شیئش را از قبل از میان
`visible_to(user, action)` پیدا می‌کند؛ وقتی از یک سرویس پرسیده شود، یک
`exists()` هزینه دارد.

---

## ۱۰. لایه‌ی ۳: فیلدهای محافظت‌شده

### ۱۰.۱ تعریفشان

* در پنل ادمین: یک مدل و یک فیلد را انتخاب کنید و محافظت‌شده علامتش بزنید؛
* در کد: `build_permissions(..., protected_fields=('price',))`.

هر کدام، مجوزهای دیدن و ویرایش آن فیلد را می‌سازد، با همان شیوه‌ی نام‌گذاری
مجوزهای خود مدل: `shop.order_view_price` و `shop.order_edit_price` روی مدلی که
مجوزهای خودش را تعریف می‌کند، و `shop.view_order_price` و
`shop.change_order_price` روی مدلی که مجوزهای جنگو را نگه داشته. فیلد رمز عبور و
کلید اصلی نمی‌توانند محافظت شوند - اولی هیچ‌وقت نشان داده نمی‌شود، و دومی همان
چیزی است که یک ردیف با آن پیدا می‌شود - و رابطه‌ای که مدل دیگری با این مدل دارد
هم نمی‌تواند.

### ۱۰.۲ دو قانون

* **خواندن:** بدون مجوز دیدن، فیلد **حذف می‌شود** - کلیدش در جواب نیست.
* **نوشتن:** بدون مجوز ویرایش، فیلد در فرم نشان داده نمی‌شود، و مقداری که برایش
  به یک API فرستاده شود **رد می‌شود** و اسم فیلد گفته می‌شود.

فیلدی که نمی‌شود خواند، نوشتنش هم نمی‌شود: فرمی که آن را نشان دهد، مقدارش را هم
نشان می‌دهد. مجوزهای یک فیلد scope ندارند - مال شخص‌اند، نه مال ردیف (تصمیم ۱۳) -
پس دادن یکی از آن‌ها با scope رد می‌شود.

### ۱۰.۳ همه‌ی درها

| کجا | چطور |
|---|---|
| یک فرم جنگو | `ProtectedFieldsFormMixin` چیزی را که نمی‌شود خواند حذف می‌کند، و چیزی را که نمی‌شود نوشت غیرفعال نشان می‌دهد - بعد جنگو مقداری را که ردیف دارد نگه می‌دارد، هر چه فرستاده شود |
| یک ویوی جنگو | `ProtectedFieldsViewMixin` فرم را همین‌طور می‌سازد، و `readable_fields` و `writable_fields` را به تمپلیت می‌دهد |
| پنل ادمین | هر `ModelAdmin` روی `ClearanceAdminSite`، بدون mixin: از فرم، لیست، جستجو، فیلترها و مرتب‌سازی حذف می‌شود؛ جایی که نوشتنش مجاز نیست، در فرم و در `list_editable` فقط‌خواندنی است |
| یک serializer در DRF | `ProtectedFieldsSerializerMixin` حذف می‌کند، قفل می‌کند و رد می‌کند؛ و روی هر serializerی، `ModelPolicyPermission` و `PolicyPermission` چیزی را که نوشتنش مجاز نیست رد می‌کنند |
| یک تمپلیت | `{% if perms.shop.view_order_price %}` |
| کد | `readable_fields(user, Order)`، `writable_fields(user, Order)` |

کتابخانه درهایی را نگهبانی می‌کند که خودش ارائه می‌دهد؛
`Order.objects.values('price')` در کد خود پروژه، نگهبانی‌اش با خود پروژه است، و
مستندات این را می‌گوید. در 0.1 مجوزهای یک فیلد مال شخص است، نه مال ردیف.

اینکه چه چیزی محافظت‌شده است یک بار در هر درخواست خوانده می‌شود، با یک کوئری روی
کل جدول - که همان چند فیلدی را دارد که یک پروژه محافظت می‌کند - و کنار مجوزهای
شخص روی خود او نگه داشته می‌شود.

### ۱۰.۴ محافظت کردن و برداشتن محافظت

`AccessService.protect_field(model, field)` یک فیلد را علامت می‌زند و دو مجوزش را
می‌سازد؛ هنوز هیچ‌کس آن‌ها را ندارد، پس از آن به بعد فقط superuser آن فیلد را
می‌خواند، تا وقتی بسته‌ای که آن‌ها را دارد به کسی داده شود.
`unprotect_field(model, field)` هر دو را حذف می‌کند، و هر مجوزی را که از آن‌ها
داده شده. کنار مجوزهای خود کتابخانه، سه رد برقرار است:

* **فیلدی که یک scope قانونی آن را می‌خواند محافظت نمی‌شود** - آن قانون به هر کسی
  که به او می‌رسد می‌گفت فیلد چه دارد. قانون‌ها نام برده می‌شوند، و اول آن‌ها
  تغییر می‌کنند. قانونی روی فیلدی که به شکل دیگری محافظت شده - در کد، بعد از
  ذخیره شدن قانون - مثل هر قانونی که دیگر درست نیست، به هیچ ردیفی نمی‌رسد؛
* **هیچ‌کس محافظت فیلدی را که هر دو مجوزش را ندارد برنمی‌دارد** - فیلدی را به
  خودش می‌داد که هیچ‌وقت به او داده نشده (`not_held`)؛
* **فیلدی که در کد محافظت شده، در کد از محافظت خارج می‌شود**.

---

## ۱۱. لایه‌ی ۴: نقش‌ها (اختیاری)

`clearance.roles` نقش‌ها را در دیتابیس نگه می‌دارد، ساخته‌شده در پنل ادمین:

* **یک نقش** یک کد و یک اسم به هر زبان است. نقش‌ها در پنل ادمین به آدم‌ها داده
  می‌شوند (`RoleAssignment`)، و هر شخص می‌تواند چند نقش داشته باشد.
* **یک سقف** مجوزهایی است که یک نقش هرگز می‌تواند داشته باشد - یا هیچ، برای نقشی
  که محدود نیست. چیزی که به شخص اجازه داده می‌شود، همان چیزی است که دارد، محدود
  به اجتماع سقف‌های نقش‌هایش، و در Backend و بعد از همه چیز اعمال می‌شود، پس هیچ
  بسته، مجوز مستقیم یا بسته‌ی اولیه‌ای از آن رد نمی‌شود. **تغییر یک سقف مجوز
  `clearance.role_ceiling_edit` را می‌خواهد**، که تا وقتی به کسی داده نشده فقط
  superuser آن را دارد - پس مدیرهایی که بسته‌ها را مدیریت می‌کنند نمی‌توانند
  چیزی را که یک نقش می‌تواند داشته باشد بازتر کنند.
* **بسته‌های اولیه**: `RoleBundle` به هر کسی که یک نقش دارد یک بسته می‌دهد.
* **از کد**، نقش‌ها، سقف‌ها و بسته‌های اولیه را می‌شود به‌جای آن در فایل `ACCESS`
  نوشت (۵.۸)، و پنل ادمین آن‌ها را فقط‌خواندنی نشان می‌دهد.
* **جای دیگر**: پروژه‌ای که نقش‌ها را روی مدل کاربرش نگه می‌دارد - یک ستون
  `role`، `is_staff`، گروه‌های جنگو - به‌جای آن با `AttributeResolver` یا یک
  resolver مخصوص خودش آن‌ها را می‌خواند.
* **در یک policy**، `has_role(user, *roles)` جواب می‌دهد یک کار کار چه کسی است.

### ۱۱.۱ سقف چطور کار می‌کند

سقف یک شخص اجتماع سقف‌های نقش‌هایش است. کسی که هیچ نقشی ندارد سقفی ندارد، و
کسی که حتی یکی از نقش‌هایش محدود نیست هم سقفی ندارد: نقش‌ها محدود می‌کنند، جای
بسته‌ها را نمی‌گیرند. یک نقش تازه محدود است و هیچ چیزی را اجازه نمی‌دهد، پس دادن
آن به کسی تا وقتی سقفش تعیین نشده همه چیز را از او می‌گیرد - که جهت امن است.

سقف و بسته‌های شروع، شرط‌هایی داخل همان کوئری‌هایی‌اند که backend و مجوزها از
قبل می‌سازند (`clearance.limits`)، پس پرسیدن درباره‌ی کسی که نقش دارد هزینه‌ی
بیشتری ندارد. هسته هیچ چیزی از `clearance.roles` import نمی‌کند: خود اپ موقع
شروع آن‌ها را برقرار می‌کند.

`AttributeResolver` یک فیلد از مدل کاربر را می‌خواند - یک ستون، هرگز یک property
- تا بتواند داخل همان کوئری خوانده شود. هر چیز دیگری resolver خود پروژه است که با
querysetها جواب می‌دهد.

### ۱۱.۲ تغییر دادن نقش‌ها

هر تغییری از طریق `RoleService` انجام می‌شود، زیر قواعد هسته و دو قاعده‌ی دیگر:

* **سقف فقط با `role_ceiling_edit` تغییر می‌کند** - تعیین کردنش، برداشتنش، و هر
  کاری که سقفی را از کسی برمی‌دارد: حذف یک نقش محدود، یا گرفتن یک نقش محدود از
  یک شخص؛
* **هیچ‌کس چیزی را که نقش خودش دارد تغییر نمی‌دهد** - سقفش، بسته‌های شروعش، یا
  اینکه اصلاً وجود داشته باشد.

بسته‌های شروع مثل بسته‌ها داده می‌شوند: فقط توسط کسی که چیزی را که می‌دهد دارد.
نقش‌هایی که از مدل کاربر خوانده می‌شوند همان‌جا داده می‌شوند، نه اینجا.

---

## ۱۲. قواعد ایمنی

پنل ادمین همه چیز را مدیریت می‌کند، پس کسی که می‌تواند دسترسی‌ها را مدیریت کند،
نباید بتواند همه چیز را به خودش بدهد. هر تغییری - در یک صفحه یا در کد - از طریق
`AccessService` انجام می‌شود، که این‌ها را رد می‌کند:

* **تغییر دادن دسترسی خودتان** - بسته‌ها، مجوزهای مستقیم، سلب‌ها، نقش‌هایتان، یا
  بسته‌ای که خودتان دارید. کس دیگری که دسترسی‌ها را مدیریت می‌کند این کار را
  می‌کند، یا superuser؛
* **دادن چیزی که خودتان ندارید** - گذاشتن یک مجوز در یک بسته، دادن بسته‌ای که آن
  را دارد، یا دادن مستقیم آن، وقتی خودتان آن را ندارید؛ و **با scopeی که خودتان
  آن مجوز را با آن ندارید**، مگر اینکه آن را با `all` داشته باشید - وگرنه یک
  همکار می‌توانست آن را به شما برگرداند؛
* **تغییری که بعد از آن جز superuser هیچ‌کس نتواند دسترسی‌ها را مدیریت کند** -
  آخرین کسی که `permission_edit` را دارد، آن را از دست بدهد؛
* **تغییر ردیف‌های یک scope قانونی که مجوزهای خودتان در آن است** (۹.۲)؛
* **برداشتن محافظت فیلدی که هر دو مجوزش را ندارید** (۱۰.۴)؛
* **آزاد کردن مقدار یک اکشن وضعیت، یا حذفش، بدون داشتن آن روی همه‌ی ردیف‌ها؛ و
  اینکه بگذارید اکشنی که خودتان دارید از مقدارهای بیشتری بنویسد** (۸.۱)؛
* **تغییر چیزی که صاحبش فایل `ACCESS` است** - هر کسی، superuser هم؛ فقط sync آن
  را تغییر می‌دهد (۵.۸)؛
* **برداشتن سقف از کسی بدون `role_ceiling_edit`، یا تغییر چیزی که نقش خودتان
  دارد** (۱۱.۲)؛
* **بازتر کردن یک سقف**، بدون `role_ceiling_edit`.

هر رد شدنی می‌گوید کدام قاعده بوده، و هر تغییری یک signal است.

---

## ۱۳. از ویو تا policy

### ۱۳.۱ DRF

`ModelPolicyPermission` مدل ویو را پیدا می‌کند - از `queryset`، یا از
`get_queryset()`ای که برای خود ویو نوشته شده - و از policy همان مدل می‌پرسد.
`PolicyPermission` از policyای می‌پرسد که ویو در `policy` نام برده، برای ویویی
که مدل ندارد. هر دو این‌ها را به hookها می‌رسانند: `list`/`retrieve` به
`can_list`/`can_view`، `create` به `can_create`، `update`/`partial_update` به
`can_edit`، `destroy` به `can_delete`، یک `@action` به مجوزی که برایش پیدا شده
یا به `custom_actions` در policy، و یک `APIView` بر اساس متد HTTP - که
`policy_action` می‌تواند اکشن دیگری را نام ببرد؛ متدی که به هیچ اکشنی نمی‌رسد رد
می‌شود. سطح شیء هم همین جدول است، با خود شیء.

**روی هر serializerی، نوشتن نگهبانی می‌شود.** قبل از اینکه serializer اجرا شود،
یک `create` یا `edit` که مقداری می‌فرستد که شخص اجازه‌ی نوشتنش را ندارد - یک فیلد
محافظت‌شده، یا مقداری که یک اکشن وضعیت ادعایش کرده - با 400 رد می‌شود و اسم فیلد
گفته می‌شود؛ پس serializerی که بدون این کتابخانه نوشته شده نمی‌تواند چیزی را که
نباید، بنویسد. `ProtectedFieldsSerializerMixin` هم به تنهایی همین‌طور رد می‌کند،
برای serializerی که بیرون از چنین ویویی به کار می‌رود؛ شخص را از request، یا از
`context['user']`، می‌خواند، و اگر هیچ‌کدام نباشد ساخته نمی‌شود.

برای خواندن چنین پشتوانه‌ای نیست - یک permission class نمی‌تواند جواب را تغییر
دهد - پس E003 موقع راه‌اندازی، ویویی را که از policy یک مدل می‌پرسد و serializerش
همه‌ی فیلدها را نشان می‌دهد، رد می‌کند. این برای همه‌ی مدل‌ها برقرار است، نه فقط
مدلی که امروز فیلد محافظت‌شده دارد: فیلدی که فردا در پنل ادمین محافظت شود، وگرنه
با serializerی که هیچ‌کس تغییرش نداده نشان داده می‌شد.

### ۱۳.۲ ویوهای جنگو

`PolicyRequiredMixin` نوع کار را از نوع ویو می‌خواند - `ListView` یعنی `list`،
`DetailView` یعنی `view`، `CreateView` یعنی `create`، `UpdateView` یعنی
`edit`، `DeleteView` یعنی `delete` - یا از `policy_action` می‌گیرد؛ ویویی که نشود
نوع کار را از آن خواند `ImproperlyConfigured` است. هر ویو اول در `dispatch` بدون
شیء می‌پرسد؛ ویویی که شیء دارد دوباره با آن می‌پرسد. می‌شود `policy` را ننوشت، و
آن وقت از policy خود مدل پرسیده می‌شود.

---

## ۱۴. پنل ادمین

روی پنل ادمین خود جنگو ساخته می‌شود: با ظاهر خودش، حالت تاریکش، و چیدمان
راست‌به‌چپش وقتی زبان فارسی است. بدون ابزار build - تمپلیت، یک فایل استایل و
اسکریپت‌های ساده.

| صفحه | مدیر سایت آنجا چه کار می‌کند |
|---|---|
| **نمای کلی** | بسته‌ها، نقش‌ها، آدم‌هایی که دسترسی دارند، و چیزهایی که `clearance_check` پیدا کرده را می‌بیند |
| **بسته‌ها** | یک بسته را به شکل یک **جدول** می‌سازد و تغییر می‌دهد: هر مدل در یک سطر، هر اکشن در یک ستون، یک تیک، و یک scope کنار هر مجوز تیک‌خورده؛ و بسته را به آدم‌ها می‌دهد |
| **scope ردیف** | برای یک مدل scope قانونی می‌سازد، scopeهای کد را کنارش می‌بیند، و اینکه کدام مجوزها از هر کدام استفاده می‌کنند |
| **فیلدهای محافظت‌شده** | فیلدها را، مدل به مدل، علامت می‌زند یا علامتشان را برمی‌دارد |
| **اکشن‌ها** | اکشن وضعیت می‌سازد؛ اکشن‌هایی را که در کد پیدا شده‌اند، و آن‌هایی را که از کد حذف شده‌اند، می‌بیند |
| **نقش‌ها** | نقش می‌سازد، بسته‌های اولیه‌شان را تعیین می‌کند، و - با `role_ceiling_edit` - سقفشان را |
| **آدم‌ها** | وضعیت کامل یک شخص: نقش‌ها، بسته‌ها، مجوزهای مستقیم همراه scopeها، سلب‌ها همراه دلیل - و چیزی که در نهایت به او اجازه داده می‌شود، با اینکه هر مجوز از کجا آمده |
| **مجوزها** | هر مجوز، فقط‌خواندنی، با اینکه چه کسی و چطور آن را دارد |

هر صفحه از طریق `AccessService` و زیر قواعد ایمنی می‌نویسد، و مجوزهای خود
کتابخانه را لازم دارد: `permission_view` برای دیدن، و `permission_create`،
`_edit` و `_delete` برای تغییر.

چیزی که فایل `ACCESS` یا کد تعریف کرده، با برچسب *تعریف‌شده در کد* و
فقط‌خواندنی نشان داده می‌شود: اگر در پنل ادمین تغییر می‌کرد، با sync بعدی
برمی‌گشت. بدون `django.contrib.admin`، هیچ‌کدام از این صفحه‌ها وجود ندارند و
هیچ چیز دیگری تغییر نمی‌کند.

### ۱۴.۱ همه‌ی صفحه‌های پنل ادمین

یک پروژه سایت ادمین کتابخانه را با نوشتن اپ ادمین آن به جای اپ ادمین جنگو به کار
می‌برد - و هیچ چیز دیگری در پروژه تغییر نمی‌کند:

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
]
```

`ClearanceAdminSite` به هر `ModelAdmin`ی که ثبت می‌کند، و به هر inline آن،
hookهای کتابخانه را می‌دهد، پس کلاس‌های ادمین پروژه همان‌طور می‌مانند که مستندات
جنگو می‌گوید:

* **چه کسی** - `has_view_permission` و بقیه از policy مدل می‌پرسند، و اگر شیئی
  باشد همراه با آن؛
* **کدام ردیف‌ها** - لیست تغییرات، و هر شیئی که باز می‌شود، از ردیف‌هایی می‌آید
  که شخص به آن‌ها می‌رسد؛
* **کدام فیلدها** - فیلد محافظت‌شده‌ای که شخص نمی‌تواند بخواند، از فرم، لیست،
  جستجو، فیلترها و مرتب‌سازی حذف می‌شود - جستجو یا مرتب کردن بر اساس آن می‌گفت
  چه دارد؛ فیلدی که می‌تواند بخواند ولی نمی‌تواند بنویسد، در فرم و در
  `list_editable` فقط‌خواندنی است؛ فیلدی که یک اکشن وضعیت می‌نویسد فقط مقدارهایی
  را نشان می‌دهد که شخص اجازه دارد بگذارد؛
* **کدام اکشن‌ها** - اکشن ادمینی که پروژه نوشته، فقط به کسی نشان داده می‌شود که
  مجوزش را دارد، و فقط روی ردیف‌های انتخاب‌شده‌ای اجرا می‌شود که scopeاش به آن‌ها
  می‌رسد؛ اکشنی که `permissions=` جنگو را نام می‌برد تصمیمش با جنگوست، و
  `delete_selected` روی ردیف‌هایی اجرا می‌شود که شخص اجازه‌ی حذفشان را دارد.

روی مدل کاربر، گروه‌ها و مجوزهای یک شخص فقط‌خواندنی‌اند - در صفحه‌ی آدم‌ها و زیر
قواعد امنیتی تغییر می‌کنند - و فقط superuser کسی را superuser می‌کند. صفحه‌ی
گروه‌های خود جنگو برداشته می‌شود: یک بسته همان گروه است، و آن صفحه همه‌ی قواعد را
دور می‌زد. سایت ادمینی که مال کتابخانه نباشد موقع راه‌اندازی رد می‌شود (E016)؛
پروژه‌ای که سایت ادمین خودش را دارد از `ClearanceAdminSite` ارث می‌برد.

### ۱۴.۲ صفحه‌ها

* **scopeهای ردیف** - هر scopeی که هر مدل ارائه می‌دهد، در کد یا به شکل قانون، با
  مجوزهایی که از آن استفاده می‌کنند؛ و قانونی که به هیچ ردیفی نمی‌رسد علامت
  می‌خورد. سازنده‌ی قانون فیلدهایی را پیشنهاد می‌دهد که یک قانون می‌تواند بخواند -
  فیلدهای خود مدل، و یک رابطه جلوتر، هرگز یک فیلد محافظت‌شده یا رمز عبور - و یک
  اسکریپت شرط اضافه و حذف می‌کند؛ بدون اسکریپت هم صفحه کار می‌کند، سه شرط در هر
  بار. هر شرط موقع ذخیره بررسی می‌شود، و هر شرطی که غلط است نام برده می‌شود.
* **فیلدهای محافظت‌شده** - فیلدهای هر مدل، کدام محافظت‌شده‌اند و چطور - در کد، یا
  اینجا - و دو مجوزشان.
* **اکشن‌ها** - اکشن‌های وضعیت در دو قدم ساخته می‌شوند، اول مدل و بعد فیلدش، تا
  مقدارها پیشنهاد شوند نه اینکه تایپ شوند؛ اکشن‌هایی که در کد پیدا شده‌اند؛ و
  مجوزهایی که دیگر هیچ چیزی بررسی‌شان نمی‌کند.
* **نقش‌ها** - با `clearance.roles`: همه‌ی نقش‌ها، و اسم، سقف، بسته‌های شروع و
  آدم‌های هر کدام؛ صفحه‌ی یک شخص نقش‌هایش، بسته‌هایی که با آن‌ها شروع می‌کند، و
  چیزهایی را که سقفش جلویشان را می‌گیرد نشان می‌دهد.

هر کدام یک `PageSet` است که کنار بقیه اضافه می‌شود؛ همه از طریق سرویس‌ها
می‌نویسند. هیچ صفحه‌ای، در هیچ جهتی، از صفحه‌ی نمایش پهن‌تر نیست - یک جدول پهن در
کادر خودش اسکرول می‌شود - و یک تست مرورگر (`nox -s browser`) این را، اسکریپت
سازنده‌ی قانون را، و راست‌به‌چپ خوانده شدن فارسی را تضمین می‌کند.

### ۱۴.۳ چیزی که دیتابیس می‌گوید غلط است

`clearance_check` - و صفحه‌ی نمای کلی - چیزی را می‌گویند که فقط دیتابیس می‌تواند
بگوید. **خطاها** دستور را fail می‌کنند، چون هر کدام چیزی است که ساخته شده تا
دسترسی بدهد و حالا بی‌صدا هیچ دسترسی‌ای نمی‌دهد: یک scope قانونی که دیگر درست
نیست، یک اکشن وضعیت که فیلد یا مقدارهایش دیگر وجود ندارند، یک مجوز که scopeاش را
مدلش دیگر ارائه نمی‌دهد. **هشدارها** بدون fail شدن فهرست می‌شوند: مجوزی بدون scope
روی مدلی که پیش‌فرضش به هیچ ردیفی نمی‌رسد، و مجوزی که هیچ چیزی توضیحش نمی‌دهد -
اکشنی که از کد حذف شده، یا مجوزی که با دست ساخته شده.
---

## ۱۵. تنظیمات

همه زیر `CLEARANCE`؛ حالت پیش‌فرض به هیچ‌کدام نیاز ندارد. کلیدی که کتابخانه
نمی‌شناسد رد می‌شود (E011).

| کلید | پیش‌فرض | معنی |
|---|---|---|
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AssignmentResolver'` | نقش‌های هر شخص از کجا خوانده شود |
| `ROLE_ATTRIBUTE` | `'role'` | چیزی که `AttributeResolver` می‌خواند |
| `ACCESS` | `None` | دسترسی‌هایی که در کد تعریف شده - بسته‌ها، نقش‌ها، سقف‌ها، اکشن‌های وضعیت - که `clearance_sync` اعمالشان می‌کند |
| `SYNC_ON_MIGRATE` | `False` | اجرای `clearance_sync`، یک بار در پایان یک `migrate` رو به جلو |
| `RULE_DEPTH` | `3` | فیلد یک قانون از چند رابطه می‌تواند عبور کند |

---

## ۱۶. مدل‌ها

| اپ | مدل | چه چیزی نگه می‌دارد |
|---|---|---|
| `clearance` | `ScopeGrant` | `group` یا `user` (دقیقاً یکی)، `permission`، `scope` |
| `clearance` | `PermissionRevocation` | `user`، `permission`، `revoked_by`، `reason`، `revoked_at` |
| `clearance` | `ScopeRule` | `content_type`، `code`، `name`، `match` (همه یا هر کدام)، `conditions` |
| `clearance` | `ProtectedField` | `content_type`، `field` - همراه دو مجوزی که ساخته |
| `clearance` | `StatusAction` | `content_type`، `code`، `name`، `field`، `to_values`، `from_values` - همراه مجوزش |
| `clearance` | `Declared` | چیزی که فایل `ACCESS` صاحبش است - یک بسته، یک نقش، یک اکشن وضعیت - تا sync بداند چه چیزی را می‌تواند حذف کند، و پنل ادمین آن را فقط‌خواندنی نشان دهد |
| `clearance.roles` | `Role` | `code`، `name`، `limited` |
| `clearance.roles` | `RoleAssignment` | `user`، `role`، `assigned_by`، `assigned_at` |
| `clearance.roles` | `RoleCeiling` | `role`، `permission` |
| `clearance.roles` | `RoleBundle` | `role`، `group` |
| `clearance.translations` | `PermissionTranslation`، `BundleTranslation`، `RoleTranslation` | یک اسم و یک توضیح برای هر زبان |

هر کلید خارجی به یک شخص `settings.AUTH_USER_MODEL` است.

---

## ۱۷. بررسی‌های سیستمی (system checks)

| شناسه | چه زمانی |
|---|---|
| `clearance.E001` | `ACCESS` قابل خواندن نیست، بخشی دارد که هیچ اپ نصب‌شده‌ای آن را نمی‌خواند، یا چیزی می‌گوید که نمی‌تواند باشد - مجوزی که به شکل `app_label.codename` نیست، مدلی که نصب نیست، فیلد یا مقداری از یک اکشن وضعیت که مدلش ندارد |
| `clearance.E002` | `scopes` یک `ScopedQuerySet` با متدهای `scope_<x>` آن نمی‌خواند، یا `default_scope` آن ارائه نشده |
| `clearance.E003` | یک ویوی DRF که از policy یک مدل می‌پرسد، مدل را بدون حذف فیلدهای محافظت‌شده‌اش serialize می‌کند |
| `clearance.E006` | `ClearanceBackend` در `AUTHENTICATION_BACKENDS` نیست |
| `clearance.E007` | `ModelBackend` کنار `ClearanceBackend` است - همه‌ی سلب‌ها را برمی‌گرداند |
| `clearance.E008` | `clearance.roles` یا `clearance.translations` بدون `'clearance'`، یا قبل از آن، نصب شده |
| `clearance.E009` | یک ویوی `PolicyRequiredMixin`، یا یک ویوی DRF که با policy محافظت شده، نمی‌تواند از هیچ policyای بپرسد |
| `clearance.E010` | `ROLE_RESOLVER` یا `ROLE_ATTRIBUTE` قابل استفاده نیست |
| `clearance.E011` | `CLEARANCE` دیکشنری نیست، کلیدی دارد که کتابخانه نمی‌شناسد، یا مقداری که نمی‌تواند به کار ببرد - `RULE_DEPTH` کمتر از یک |
| `clearance.E012` | فیلدی که در کد محافظت‌شده تعریف شده، فیلدی از مدلش نیست، یا نمی‌تواند محافظت شود - کلید اصلی، رمز عبور، رابطه‌ی یک مدل دیگر |
| `clearance.E013` | اکشنی که در کد پیدا شده نمی‌تواند یک مجوز بسازد - policyاش مدلی ندارد، یا اسمش بیش از حد بلند است |
| `clearance.E014` | یک مدل مجوزهایش را با `build_permissions` تعریف کرده ولی مجوزهای خود جنگو را هم نگه داشته - `default_permissions = ()` جا افتاده |
| `clearance.E015` | اکشن وضعیتی که در کد تعریف شده، فیلد یا مقداری را نام می‌برد که مدلش ندارد |
| `clearance.E016` | یک سایت ادمین مال کتابخانه نیست: صفحه‌هایش از policyها نمی‌پرسیدند، و همه‌ی فیلدهای محافظت‌شده را نشان می‌دادند |

E004 و E005 کنار گذاشته شده‌اند. E004 ویوی scoped روی manager معمولی را رد
می‌کرد، و حالا هر querysetی scope می‌گیرد؛ E005 سقف‌هایی را که در کد نوشته
می‌شدند بررسی می‌کرد، و سقف‌ها حالا در دیتابیس‌اند.

`clearance_check` (۱۴.۳)، که دیتابیس را می‌خواند، مجوزهای بدون scope، scopeهای قانونی و
اکشن‌های وضعیتی که فیلدشان دیگر وجود ندارد، اکشن‌هایی که از کد حذف شده‌اند، و
مجوزهایی که هیچ‌کس ندارد را فهرست می‌کند.

---

## ۱۸. Signalها

هر کدام بعد از commit شدن تراکنش فرستاده می‌شود، همراه شخص یا بسته، چیزی که
تغییر کرده و `actor`: `bundle_created`، `bundle_changed`، `bundle_deleted`،
`bundle_given`، `bundle_taken`، `permission_granted`، `permission_revoked`،
`permission_restored`، `scope_changed`، `scope_rule_saved`،
`scope_rule_deleted`، `field_protected`، `field_unprotected`،
`status_action_saved`، `status_action_deleted`، `actions_found`، و با
`clearance.roles`، `role_saved`، `role_deleted`، `role_assigned`،
`role_unassigned` و `ceiling_changed`.

---

## ۱۹. سازگاری

| | پشتیبانی | تست در CI |
|---|---|---|
| Python | 3.11 تا 3.14 | همه‌شان |
| Django | 5.2 LTS، 6.0، 6.1 | هر کدام با همه‌ی نسخه‌های پایتونی که پشتیبانی می‌کند |
| Django REST framework | 3.16 و بالاتر، اختیاری | آخرین نسخه |
| دیتابیس | هر چیزی که جنگو پشتیبانی می‌کند | PostgreSQL و SQLite |
| مرورگر، برای پنل ادمین | هر چیزی که پنل ادمین جنگو پشتیبانی می‌کند | آخرین نسخه‌ی Chromium، با Playwright |

---

## ۲۰. قراردادهای این ریپو

* **کد فقط به انگلیسی**؛ هر پیام برای ترجمه علامت‌گذاری می‌شود و فارسی در
  `src/clearance/locale/fa/` است.
* **مستندات به انگلیسی و فارسی** که با هم تغییر می‌کنند.
* **docstring هر ماژول می‌گوید چرا وجود دارد**؛ و هر قاعده، بدون آن چه چیزی خراب
  می‌شد.
* **اسم تست‌ها از رفتاری است که نگه می‌دارند**؛ هزینه با
  `django_assert_num_queries` شمرده می‌شود؛ صفحه‌های پنل ادمین در مرورگر تست
  می‌شوند.
* **ruff** و **mypy** (strict)؛ هر مرحله یک pull request.

---

## ۲۱. مرحله‌ها

| مرحله | تحویل | |
|---|---|---|
| 0 | طراحی | انجام شده |
| 1 | اسکلت و CI | انجام شده |
| 2 | مجوزها، policyها، registry | انجام شده |
| 3 | تنظیمات، ویوهای جنگو، decorator، checkها - ساخته‌شده حول نقش‌ها | انجام شده؛ در 3b بازسازی می‌شود |
| **3b** | هسته‌ی لایه‌های ۱ و ۲: مجوزهای پیش‌فرض و سفارشی، `ModelPolicy`، `ScopeGrant`، `PermissionRevocation`، `ClearanceBackend`، `grants`، `AccessService` همراه **قواعد ایمنی**، مجوزهای خود کتابخانه، scopeهای کد و `visible_to(user, action)`، hookهایی که scope را رعایت می‌کنند؛ کد نقش‌های مرحله‌ی ۳ به مرحله‌ی ۹ منتقل می‌شود | |
| 4 | سازنده‌ی قانون: `ScopeRule`، با بررسی شرط‌هایش و تبدیلشان به `Q` | |
| 5 | فیلدهای محافظت‌شده: در کد و در دیتابیس، زیر قواعد امنیتی؛ فرم‌ها، ویوها، تمپلیت‌ها و کد - در پنل ادمین همراه خود پنل ادمین، در مرحله‌ی ۸ | |
| 6 | اکشن‌ها: اکشن‌های وضعیت، در کد و در دیتابیس، زیر قواعد امنیتی، و در فرم‌ها؛ اکشن‌هایی که در ویوهای جنگو پیدا می‌شوند؛ policyای که اکشن بدون hook را با مجوزش تصمیم می‌گیرد | |
| 7 | DRF: `ModelPolicyPermission`، `PolicyPermission`، ویوست‌ها، mixin مربوط به serializer که فیلدهای محافظت‌شده و مقدارهای وضعیت را رد می‌کند، `@action`هایی که پیدا می‌شوند، و checkهایشان | |
| 8 | پنل ادمین، بخش اول: نمای کلی، بسته‌ها به شکل جدول، آدم‌ها، مجوزها؛ هر `ModelAdmin` که `permission_for` را می‌پرسد، فیلدهای محافظت‌شده را پنهان و قفل می‌کند، مقدارهای وضعیت را محدود می‌کند، و اکشن‌هایش را فقط به کسی که آن‌ها را دارد نشان می‌دهد | |
| 9 | `clearance.roles`: نقش‌ها، سقف‌ها، بسته‌های اولیه، resolverها - و صفحه‌هایشان | |
| 10 | دسترسی به‌صورت کد: فایل `ACCESS`، `clearance_sync` با `--dry-run` و `--check`، `SYNC_ON_MIGRATE`، فقط‌خواندنی در پنل ادمین | |
| 11 | پنل ادمین، بخش دوم: صفحه‌های سازنده‌ی قانون، فیلدهای محافظت‌شده و اکشن‌ها؛ راست‌به‌چپ؛ تست در مرورگر؛ `clearance_check` و یافته‌های صفحه‌ی نمای کلی | |
| 12 | `clearance.translations` | |
| 13 | مستندات، یک پروژه‌ی نمونه، کاتالوگ فارسی | |
| 14 | استفاده در iranbobco؛ تگ `0.1.0`، public کردن، انتشار | |

---

## ۲۲. چیزی که این ویرایش در کد ساخته‌شده عوض می‌کند

* **مجوزهای مرحله‌ی ۲** مجوزهای پیش‌فرض را هم می‌گیرند: `permission_for(model,
  action)` به هر دو جواب می‌دهد، و policy از آن می‌پرسد.
* **مرحله‌ی ۳** خواننده‌ی تنظیمات، `PolicyRequiredMixin`، decorator و checkهایش
  را نگه می‌دارد. محدودسازی ردیف بر اساس نقش، به محدودسازی بر اساس مجوز تبدیل
  می‌شود، و resolverهایش به `clearance.roles` منتقل می‌شوند.

## ۲۳. بعد از 0.1

* **مجوز روی یک ردیف** - «علی می‌تواند سفارش ۴۲ را ویرایش کند».
* **فیلدهای محافظت‌شده با scope ردیف** - قیمت سفارش‌های شعبه‌ی خودش.
* **قانون‌هایی که در چند سطح ترکیب می‌شوند** - (الف و ب) یا ج.
* **endpointهای REST** برای صفحه‌ی دسترسی و برای «من چه کارهایی می‌توانم بکنم».

---

## ۲۴. تصمیم‌ها

تصمیم‌های صاحب پروژه:

1. هر import اسم ماژولش را می‌آورد.
2. صاحب حق کپی amir mohammad kashanchian است.
3. قدیمی‌ترین نسخه‌ی پایتون 3.11 است.
4. *(با ۲۷ اصلاح شده)* resolver پیش‌فرض نقش `user.role` را می‌خواند.
5. ویوهای خود جنگو همان پلی را می‌گیرند که DRF دارد.
6. پنل ادمین مجوزها را نشان می‌دهد و بسته می‌سازد.
7. مجوزها و بسته‌ها در 0.1 به هر زبانی نام‌گذاری می‌شوند.
8. بسته‌های دسترسی هسته‌اند؛ پروژه به نقش نیازی ندارد.
9. scope ردیف برای هر مجوز داخل بسته انتخاب می‌شود.
10. نقش‌ها محدود می‌کنند و می‌توانند بسته‌ی اولیه بدهند - که سقف آن را هم محدود
    می‌کند.
11. فیلدها می‌توانند محافظت شوند، هر کدام با مجوز دیدن و ویرایش خودش.
12. مجوزی که بدون scope داده شده، به `default_scope` مدل می‌رسد - و وقتی
    برنامه‌نویس هیچ‌کدام را نام نبرده، به هیچ ردیفی.
13. در 0.1، مجوزهای یک فیلد مال شخص است، نه با scope ردیف.
14. *(جایش را ۲۳ گرفته)* سقف‌ها در کد نوشته می‌شوند.
15. فیلد محافظت‌شده حذف می‌شود وقتی خواندنش مجاز نیست، و مقداری که برایش فرستاده
    شود رد می‌شود وقتی نوشتنش مجاز نیست.
16. `'clearance'` یک اپ با مدل است که لایه‌های ۱ تا ۳ را نگه می‌دارد.
17. همه‌ی لایه‌ها اختیاری‌اند؛ تنها چیز اجباری `ClearanceBackend` است.
18. **پیش‌فرض و سفارشی برای هر مدل انتخاب می‌شوند**: مجوزهای خود جنگو به‌طور
    پیش‌فرض، و `build_permissions` برای مدلی که مجوزهای خودش را تعریف می‌کند.
19. **پنل ادمین هر کاری را که کتابخانه می‌تواند انجام می‌دهد.**
20. **اکشن‌های وضعیت** در پنل ادمین و بدون کد ساخته می‌شوند.
21. **اکشن‌ها در کد پیدا می‌شوند** - `@action` در DRF، `policy_action`،
    `@policy_required`، اکشن‌های ادمین - و با `migrate` مجوزشان را می‌گیرند.
22. **scope ردیف در پنل ادمین** از قانون‌های ساده ساخته می‌شود، در 0.1، کنار
    scopeهای کد.
23. **نقش‌ها و سقف‌ها در دیتابیس نگه داشته می‌شوند** و در پنل ادمین ساخته
    می‌شوند؛ **تغییر یک سقف مجوز `role_ceiling_edit` را می‌خواهد**، که به‌طور
    پیش‌فرض فقط superuser آن را دارد.
24. **مجوزهای خود کتابخانه** - `permission_view`، `_create`، `_edit`، `_delete` -
    به‌طور پیش‌فرض مال superuser هستند.
25. **قواعد ایمنی در 0.1 هستند**، چون پنل ادمین دسترسی‌ها را مدیریت می‌کند.
26. **همه‌ی انواع ویوی DRF و جنگو کار می‌کنند**، که `ModelViewSet` یکی از
    آن‌هاست.
27. **اصلاح تصمیم ۴:** حالا که نقش‌ها در پنل ادمین ساخته و داده می‌شوند، resolver
    پیش‌فرض ردیف‌های `RoleAssignment` را می‌خواند که پنل ادمین می‌نویسد؛
    `AttributeResolver`، که `user.role` را می‌خواند، برای پروژه‌ای است که نقش‌ها
    را روی مدل کاربرش نگه می‌دارد.
28. **یک قانون نمی‌تواند فیلد محافظت‌شده** یا رمز عبور کاربر را بخواند، و حداکثر
    سه رابطه دورتر می‌رود.
29. **فیلد رمز عبور و کلید اصلی نمی‌توانند محافظت شوند.**
30. **هیچ مجوزی را مدیر سایت تایپ نمی‌کند**: اکشن‌ها یا اکشن وضعیت هستند یا در
    کد پیدا می‌شوند، پس هر مجوزی که در پنل ادمین هست جایی بررسی می‌شود.
31. **مدلی که مجوزهای جنگو را کنار مجوزهای خودش نگه دارد رد می‌شود** (E014)، و
    صفحه‌های ادمین خود جنگو از `permission_for` می‌پرسند.
32. **اکشن‌های وضعیت را می‌شود در کد هم تعریف کرد**، علاوه بر ساختنشان در پنل
    ادمین.
33. **دسترسی را می‌شود به‌صورت کد نوشت** - فایل `ACCESS` - و با `clearance_sync`
    اعمال کرد، همراه `--dry-run` و `--check`.
34. **چیزی که کد تعریف کرده در پنل ادمین فقط‌خواندنی است**؛ و چیزی که پنل ادمین
    ساخته، کد به آن دست نمی‌زند.
35. **پنل ادمین اختیاری است**: بدون آن کتابخانه کامل کار می‌کند.
36. **`migrate` مجوزها را می‌سازد؛ `clearance_sync` دسترسی می‌دهد.**
    `SYNC_ON_MIGRATE` این دو را برای پروژه‌ای که یک دستور می‌خواهد به هم وصل می‌کند.
37. **فیلدی که نمی‌شود خواند، نوشتنش هم نمی‌شود**، و مجوز یک فیلد بدون scope داده
    می‌شود.
38. **فیلدی که یک scope قانونی آن را می‌خواند، تا وقتی قانون تغییر نکند محافظت
    نمی‌شود**؛ برداشتن محافظت یک فیلد هر دو مجوزش را لازم دارد.
39. **اکشنی که hook ندارد با مجوز و scopeاش تصمیم گرفته می‌شود**؛ فقط اسمی که
    هرگز نمی‌تواند یک مجوز باشد خطاست.
40. **مقدار یک اکشن وضعیت را فقط کسی آزاد می‌کند، یا خود اکشن را حذف می‌کند، که آن
    را روی همه‌ی ردیف‌ها دارد**؛ هیچ‌کس جایی را که اکشنی که خودش دارد از آن
    می‌نویسد بازتر نمی‌کند.
41. **روی هر serializer در DRF، نوشتن نگهبانی می‌شود** - توسط permission class،
    با 400 و اسم فیلد.
42. **ویوی DRF که از policy یک مدل می‌پرسد serializerش را محافظت می‌کند** (E003)،
    برای همه‌ی مدل‌ها - فیلدی می‌تواند بعداً در پنل ادمین محافظت شود.
43. **`custom_actions` هر جا که از یک policy پرسیده شود خوانده می‌شود**، نه فقط در
    DRF؛ اکشنی که آن را نگاشت می‌کند مال hook است، و برایش مجوزی ساخته نمی‌شود.
44. **پنل ادمین مال کتابخانه است**، که در `INSTALLED_APPS` به جای پنل ادمین جنگو
    نوشته می‌شود و بدون نوشتن هیچ mixinی hookهایش را به هر `ModelAdmin` می‌دهد؛
    هر سایت ادمین دیگری رد می‌شود (E016).
45. **در صفحه‌ی کاربر، گروه‌ها و مجوزهای یک شخص فقط‌خواندنی‌اند**، و در صفحه‌ی
    آدم‌ها زیر قواعد امنیتی تغییر می‌کنند؛ فقط superuser کسی را superuser می‌کند.
46. **اکشن ادمینی که `permissions=` جنگو را نام می‌برد مال جنگوست**؛ هر اکشن دیگری
    پیدا می‌شود، مجوز خودش را لازم دارد، و روی ردیف‌هایی اجرا می‌شود که scopeاش به
    آن‌ها می‌رسد.
47. **کسی که نقشی ندارد، یا حتی یکی از نقش‌هایش محدود نیست، سقفی ندارد**؛ یک نقش
    تازه محدود است و تا وقتی سقفش تعیین نشده هیچ چیزی را اجازه نمی‌دهد.
48. **برداشتن سقف از هر کسی `role_ceiling_edit` لازم دارد** - تغییر یک سقف، حذف یک
    نقش محدود، گرفتن یک نقش محدود - و هیچ‌کس چیزی را که نقش خودش دارد تغییر
    نمی‌دهد.
49. **نقش‌ها داخل کوئری خوانده می‌شوند**: `AttributeResolver` یک فیلد را می‌خواند،
    و هسته نقش‌ها را بدون import کردنشان از طریق `clearance.limits` برقرار می‌کند.
50. **اپ‌های کتابخانه نوع کلید اصلی خودشان را تعیین می‌کنند**، پس
    `DEFAULT_AUTO_FIELD` یک پروژه هرگز از آن نمی‌خواهد برایشان migration بسازد.
51. **فایل `ACCESS` صاحب چیزی است که نام می‌برد، و نه چیز دیگری**: یک sync فقط چیزی
    را حذف می‌کند که فایل یک بار نام برده، و چیزی را که پنل ادمین ساخته، وقتی فایل
    نامش را ببرد، در اختیار می‌گیرد.
52. **چیزی که صاحبش فایل است فقط با sync تغییر می‌کند** - برای هر شخصی، superuser
    هم، رد می‌شود.
53. **اینکه چه کسی یک بسته یا نقش را دارد کار فایل نیست**؛ در پنل ادمین می‌ماند.
54. **`clearance_check` روی چیزی fail می‌شود که بی‌صدا هیچ دسترسی‌ای نمی‌دهد**، و
    درباره‌ی چیزی که شاید منظور نبوده هشدار می‌دهد.
55. **یک صفحه بدون اسکریپتش هم کار می‌کند**؛ اسکریپت فقط کار را آسان‌تر می‌کند.
56. **هیچ صفحه‌ای، در هیچ جهتی، از صفحه‌ی نمایش پهن‌تر نیست**، و یک تست مرورگر این را
    تضمین می‌کند.
