# django-clearance - طراحی

> **وضعیت: پیشنهاد برای بررسی (مرحله‌ی ۰).** هنوز هیچ‌کدام از چیزهایی که
> اینجا توضیح داده شده پیاده نشده است. هر بخش به چیزی ختم می‌شود که یک
> مرحله‌ی بعدی آن را می‌سازد و تست می‌کند. هر چیزی که در بررسی تغییر کند،
> اول اینجا تغییر می‌کند.
>
> انگلیسی: [`design.md`](design.md). این سند ترجمه‌ی آن است و هر دو با هم
> به‌روز می‌شوند.

**django-clearance** - کنترل دسترسی مبتنی بر نقش، سیاست (policy) و سطح ردیف
برای جنگو. پیش‌فرض: رد.

این کتابخانه به سه سؤالی جواب می‌دهد که هر تصمیم دسترسی از آن‌ها ساخته
می‌شود. هر سؤال در یک جا جواب داده می‌شود، روی جدول‌های مجوز خود جنگو:

| سؤال | جواب‌دهنده | محل |
|---|---|---|
| **این شخص چه کاری می‌تواند بکند؟** | یک *policy* که با خود شیء در دست پرسیده می‌شود | `clearance.policies` |
| **به کدام ردیف‌ها دسترسی دارد؟** | *queryset*، محدودشده بر اساس نقش | `clearance.querysets` |
| **چیزی که دارد از کجا آمده؟** | *نقش‌هایش*، گروه‌های وصل به آن نقش‌ها، و چیزی که فقط از خود او گرفته شده | `clearance.roles` |

اصل کار جدا نگه داشتن این سه است. یک permission class فقط به سؤال اول جواب
می‌دهد. DRF متد `has_object_permission` را فقط وقتی صدا می‌زند که ویو یک
شیء مشخص را پیدا کرده باشد. پس یک endpoint لیستی که فقط با permission class
محافظت شده، همه‌ی ردیف‌های جدول را برمی‌گرداند - و هیچ خطایی هم نمی‌دهد، و
همین است که آن را خطرناک می‌کند. به همین دلیل محدودسازی ردیف‌ها کار queryset
است، و ویوستِ پایه خودش آن را اعمال می‌کند تا هیچ endpointی نتواند فراموشش
کند.

---

## ۱. اصول

1. **پیش‌فرض رد است.** هر کمبودی در تنظیمات به یک «نه» یا یک لیست خالی ختم
   می‌شود، هرگز به نشت داده:
   * کاربر ناشناس یا غیرفعال هیچ مجوزی ندارد و هیچ ردیفی نمی‌بیند؛
   * actionی از ویو که هیچ policyای آن را map نکرده رد می‌شود - هم در سطح
     action و هم در سطح شیء؛
   * نقشی که روی یک queryset هیچ hook محدودسازی ندارد، هیچ ردیفی از آن
     نمی‌بیند؛
   * نقشی که پروژه هرگز تعریفش نکرده، هیچ اثری ندارد؛
   * کاربری که هیچ نقشی ندارد، هیچ ردیف محدودشده‌ای نمی‌بیند.
2. **تنظیمات اشتباه سروصدا می‌کند.** هر چیزی که موقع بالا آمدن برنامه قابل
   بررسی است، یک system check جنگو است (`manage.py check` و هر بار
   `runserver`). پس در زمان توسعه و در CI شکست می‌خورد، نه به‌صورت یک 403 که
   کاربری گزارشش کند - یا بدتر، یک 200 که هیچ‌کس گزارشش نکند. چیزی که فقط با
   دیتابیس قابل بررسی است (مثل codenameی که وجود ندارد)، دستور مدیریتی‌ای را
   که به آن برمی‌خورد شکست می‌دهد. بخش ۹ را ببینید.
3. **جدول‌های مجوز جنگو محل ذخیره‌اند.** مجوزها ردیف‌های معمولی
   `auth_permission` هستند که `migrate` می‌سازدشان؛ گروه‌ها همان `auth.Group`
   هستند. پس `user.has_perm()`، `PermissionRequiredMixin`، `{{ perms }}` در
   تمپلیت‌ها و پنل ادمین همچنان کار می‌کنند و هیچ چیزی نیاز به همگام‌سازی
   ندارد.
4. **پرسیدن ارزان است.** فهمیدن اینکه یک شخص چه مجوزهایی دارد، همان تعداد
   کوئری‌ای را می‌زند که Backend خود جنگو می‌زند - هر قدر هم نقش، گروه و
   سلب مجوز در کار باشد. محدود کردن یک queryset یک `WHERE` اضافه می‌کند، هرگز
   یک کوئری به‌ازای هر ردیف. هر دو با تست‌هایی که تعداد کوئری را می‌شمارند
   تضمین می‌شوند.
5. **لایه‌ها اختیاری‌اند.** هسته هیچ مدل و migrationی ندارد؛ DRF یک وابستگی
   اختیاری است؛ اپ نقش‌ها یک اپ جنگوی جداست. هر پروژه همان چیزی را برمی‌دارد
   که لازم دارد.
6. **درباره‌ی بقیه‌ی چیزها نظری ندارد.** قالب پاسخ، قالب خطاها، محل ذخیره‌ی
   audit و مدل کاربر پروژه، مال خود پروژه‌اند. کتابخانه signal می‌فرستد و
   خطاهای خود جنگو و DRF را بالا می‌اندازد.

---

## ۲. قابلیت‌ها (نسخه‌ی 0.1)

چیزهایی که README فهرست خواهد کرد.

* **مجوزها در خود مدل تعریف می‌شوند.** `build_permissions('loan', 'loans',
  actions=(...))` در `Meta.permissions` نوشته می‌شود و `migrate` ردیف‌ها را
  می‌سازد. دستور همگام‌سازی لازم نیست.
* **Policy با hookهای سطح شیء.** `can_view(user, obj)` خود شیء را می‌گیرد،
  پس داشتن `loan_view` می‌تواند یعنی «وام‌هایی که مال خودت هستند».
  بازنویسی یک hook با صدا زدن `super()` شرط داشتن codename را حفظ می‌کند.
* **اکشن‌های سفارشی باید تعریف شوند.** `@action`ای که هیچ policyای آن را در
  `custom_actions` فهرست نکرده رد می‌شود، و `manage.py check` قبل از اینکه
  کسی صدایش بزند اسمش را اعلام می‌کند.
* **محدودسازی ردیف بر اساس نقش.** `Model.objects.visible_to(user)` به
  hookهای `scope_for_<role>` می‌رود. hookی که نوشته نشده هیچ ردیفی
  برنمی‌گرداند.
* **چند نقش برای هر کاربر.** ردیف‌های یک شخص اجتماع scope نقش‌هایش است؛
  مجوزهایش اجتماع گروه‌های نقش‌هایش.
* **نقش از هر جایی.** یک فیلد نقش روی مدل کاربر، یک attribute، جدول
  انتساب نقش که همراه کتابخانه می‌آید، یا resolver خود پروژه.
* **نقش‌های وصل به گروه.** کارهایی که یک نقش می‌تواند بکند، همان گروه‌های
  وصل به آن است - در دیتابیس تغییر می‌کند، یک‌جا به همه‌ی کسانی که آن نقش
  را دارند می‌رسد، و وقتی نقش کسی عوض شود هیچ چیزی جابه‌جا نمی‌شود.
* **گرفتن یک مجوز از یک نفر.** سلب مجوز (revocation) مجوزی را که گروه‌هایش
  به او می‌دهند کم می‌کند، بدون اینکه نقشش عوض شود یا برایش گروه جداگانه
  ساخته شود.
* **مجوزهای اولیه، فقط یک بار.** جدولی در کد شما، روی یک دیتابیس تازه به هر
  نقش اولین گروهش را می‌دهد - و دیگر هرگز، تا تغییراتی که بعداً در دیتابیس
  داده می‌شود سر جایش بماند.
* **هم با DRF و هم بدون آن.** یک mixin هم ویوهای class-based جنگو و هم
  ویوهای generic در DRF را محدود می‌کند؛ permission class مربوط به DRF از
  روی policy ساخته می‌شود.
* **قابل استفاده بیرون از ویو.** `policy.authorize(user, 'approve', loan)`
  از داخل یک سرویس، یک دستور مدیریتی یا یک تسک، خطای `PermissionDenied` خود
  جنگو را بالا می‌اندازد.
* **signal برای هر تغییر.** انتساب نقش، سلب مجوز، دادن مجوزهای اولیه - تا هر
  پروژه audit مخصوص خودش را بنویسد.
* **ترجمه‌شده.** همه‌ی پیام‌ها برای ترجمه علامت‌گذاری شده‌اند؛ انگلیسی و
  فارسی همراه بسته می‌آیند.
* **دارای type.** type hint در همه‌جا، و فایل `py.typed` همراه بسته.

---

## ۳. ساختار بسته

```
src/clearance/
    __init__.py            empty
    apps.py                ClearanceConfig - registers the system checks
    conf.py                reading and validating the CLEARANCE setting
    permissions.py         build_permissions, DEFAULT_ACTIONS, RECORD_ACTIONS
    registry.py            PermissionRegistry, ResourcePermission, registry
    policies.py            BasePolicy, SignedInReadPolicy
    resolvers.py           RoleResolver, AttributeResolver, roles_of(), reaches_every_row()
    querysets.py           ScopedQuerySet, SignedInReadQuerySet, OwnedQuerySet
    views.py               ScopedQuerySetMixin - Django CBVs and DRF generic views
    checks.py              the core system checks
    signals.py             every signal the library sends
    locale/fa/LC_MESSAGES/ the Persian catalogue

    drf/                   needs djangorestframework (pip install django-clearance[drf])
        __init__.py        empty
        permissions.py     PolicyPermission - the bridge from a view action to a policy hook
        viewsets.py        ScopedModelViewSet, ScopedReadOnlyViewSet
        checks.py          every @action mapped; every scoped viewset's queryset scoped

    roles/                 a Django app with models: INSTALLED_APPS += ['clearance.roles']
        __init__.py        empty
        apps.py            label 'clearance_roles'
        models.py          RoleAssignment, RoleGroup, PermissionRevocation, StartingPermissions
        backends.py        ClearanceBackend
        resolvers.py       AssignmentResolver
        services.py        assign_role, unassign_role, revoke_permission, restore_permission
        seeding.py         giving the starting permissions once
        admin.py
        migrations/
        management/commands/clearance_seed.py
```

قواعد این ساختار:

* **فایل‌های `__init__.py` خالی می‌مانند.** هر چیزی از همان ماژولی import
  می‌شود که تعریفش کرده: `from clearance.policies import BasePolicy`. نسخه
  با `importlib.metadata.version('django-clearance')` خوانده می‌شود.
* **هسته هیچ چیزی از `drf` یا `roles` import نمی‌کند.** `drf` هسته را import
  می‌کند؛ `roles` هسته را import می‌کند. این با import کردن هسته بدون نصب DRF
  و بدون اپ نقش‌ها تست می‌شود.
* **label اپ نقش‌ها `clearance_roles` است**، تا با اپی به اسم `roles` در
  پروژه تداخل نکند.

---

## ۴. API، با یک مثال

یک اپ کوچک وام: مشتری‌ها درخواست وام می‌دهند، کارشناس‌ها درخواست‌های شعبه‌ی
خودشان را بررسی می‌کنند، و مدیرها همه چیز را می‌خوانند.

### ۴.۱ تنظیمات

```python
INSTALLED_APPS += ['clearance', 'clearance.roles']

# Replaces django.contrib.auth.backends.ModelBackend - see check E006.
AUTHENTICATION_BACKENDS = ['clearance.roles.backends.ClearanceBackend']

CLEARANCE = {
    'ROLES': 'accounts.roles.Role',                       # a TextChoices, or a list of codes
    'ROLE_RESOLVER': 'clearance.roles.resolvers.AssignmentResolver',
    'EVERY_ROW_ROLES': ['admin'],
    'STARTING_PERMISSIONS': 'config.access.STARTING_PERMISSIONS',
}
```

```python
# accounts/roles.py
class Role(models.TextChoices):
    ADMIN = 'admin', _('Administrator')
    OFFICER = 'officer', _('Loan officer')
    CUSTOMER = 'customer', _('Customer')
```

### ۴.۲ مدل مجوزهایش را تعریف می‌کند

```python
from clearance.permissions import build_permissions

class Loan(models.Model):
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    branch = models.ForeignKey(Branch, ...)
    amount = models.DecimalField(...)

    objects = LoanQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        permissions = build_permissions(
            'loan', 'loans', actions=('view', 'create', 'edit', 'approve'),
        )
```

`default_permissions = ()` مجوزهای پیش‌فرض جنگو (add/change/delete/view) را
خاموش می‌کند؛ وگرنه کنار این‌ها به‌عنوان جواب دوم به همان سؤال می‌نشستند.
برچسب‌هایی که در `auth_permission.name` نوشته می‌شوند، عمداً انگلیسی و
ترجمه‌نشده‌اند: یک ترجمه‌ی lazy در آنجا موقع import حل می‌شود و یک زبان را در
migration ثابت می‌کند، و بعد `makemigrations` روی مدل‌هایی که کسی دستشان
نزده تغییر گزارش می‌دهد.

### ۴.۳ queryset می‌گوید کدام ردیف‌ها

```python
from django.db.models import Q
from clearance.querysets import ScopedQuerySet

class LoanQuerySet(ScopedQuerySet):
    def scope_for_customer(self, user):
        return Q(applicant=user)

    def scope_for_officer(self, user):
        return Q(branch__officers=user)
    # No scope_for_admin: 'admin' is in EVERY_ROW_ROLES, so it sees every row
    # unless this queryset says otherwise.
```

### ۴.۴ policy می‌گوید چه کاری مجاز است

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class LoanPolicy(BasePolicy):
    app_label = 'loans'
    codename = 'loan'
    custom_actions = {'approve': 'can_approve'}

    def can_approve(self, user, obj=None):
        if not self.has(user, 'approve'):
            return False
        if obj is None:
            return True
        return obj.applicant_id != user.pk

loan_access = registry.register(LoanPolicy)
```

`registry.register` دو چیز را رد می‌کند: policy دوم برای همان codename، و
ورودی‌ای در `custom_actions` که به hookی اشاره کند که policy ندارد.

### ۴.۵ ویو فقط تعریف می‌کند

```python
from clearance.drf.viewsets import ScopedModelViewSet

class LoanViewSet(ScopedModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer
    permission_classes = [loan_access.drf_class]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        loan = self.get_object()   # only among visible_to(user), then can_approve(user, loan)
        ...
```

یک ویوی معمولی جنگو هم از همان mixin استفاده می‌کند:

```python
from clearance.views import ScopedQuerySetMixin

class LoanListView(ScopedQuerySetMixin, ListView):
    queryset = Loan.objects.all()
```

### ۴.۶ بیرون از ویو

```python
loan_access.policy.allows(user, 'approve', loan)      # -> bool
loan_access.policy.authorize(user, 'approve', loan)   # raises django's PermissionDenied
Loan.objects.visible_to(user)
```

### ۴.۷ نقش‌ها، گروه‌ها و سلب مجوز

```python
# config/access.py - read once, on a new database
STARTING_PERMISSIONS = {
    'admin': ['loans.loan_view'],
    'officer': ['loans.loan_view', 'loans.loan_approve'],
    'customer': ['loans.loan_view', 'loans.loan_create'],
}
```

```bash
python manage.py migrate
python manage.py clearance_seed
```

```python
from clearance.roles.services import assign_role, revoke_permission

assign_role(person, 'officer', by=admin)
revoke_permission(person, 'loans.loan_approve', by=admin, reason='Under review')
person.has_perm('loans.loan_approve')   # False - the officer group still gives it to everybody else
```

---

## ۵. چند نقش

### ۵.۱ نقش‌های یک شخص از کجا می‌آیند

`clearance.resolvers.roles_of(user)` یک `frozenset` از کدهای نقش برمی‌گرداند.
این را از resolver تنظیم‌شده می‌پرسد و تا آخر درخواست روی خود شیء کاربر cache
می‌کند.

| resolver | چه چیزی را می‌خواند | هزینه |
|---|---|---|
| `clearance.resolvers.AttributeResolver` (پیش‌فرض) | `user.<ROLE_ATTRIBUTE>` - یک کد، یا مجموعه‌ای از کدها | هیچ |
| `clearance.roles.resolvers.AssignmentResolver` | ردیف‌های `RoleAssignment` | یک کوئری، یک بار در هر درخواست؛ داخل کوئری مجوزها هیچ (۵.۲) |
| resolver خودتان | از `RoleResolver` ارث ببرید و `roles_of(user)` را پیاده کنید | به عهده‌ی خودتان |

یک resolver می‌تواند `roles_subquery(user)` را هم پیاده کند که یک queryset از
کدهای نقش برمی‌گرداند. Backend به‌جای `roles_of` از آن استفاده می‌کند، تا
نقش‌ها داخل همان کوئری مجوزها پیدا شوند، نه قبل از آن.

کدی که resolver برمی‌گرداند ولی `ROLES` تعریفش نکرده، هیچ اثری ندارد و یک
بار به‌صورت هشدار در لاگ ثبت می‌شود.

### ۵.۲ یک شخص چه مجوزهایی دارد

```
held = direct grants (user_permissions)
     + permissions of every group linked to any of their roles (RoleGroup)
     + permissions of their own groups (user.groups)
     - their revocations (PermissionRevocation)      <- subtracted from groups only
```

سلب مجوز، مجوزی را که مستقیم به شخص داده شده لغو نمی‌کند: سلب کردن مجوزی که
مستقیم داده شده، به‌جایش همان اعطا را حذف می‌کند (`revoke_permission` بسته
به مورد، هر دو کار را می‌کند). superuser مثل خود جنگو همه‌ی مجوزها را دارد.

`ClearanceBackend` نیمه‌ی گروهیِ `ModelBackend` را بازنویسی می‌کند و cache آن
را نگه می‌دارد، پس `has_perm` دقیقاً همان تعداد کوئری‌ای را می‌زند که
`ModelBackend` می‌زند.

### ۵.۳ یک شخص کدام ردیف‌ها را می‌بیند

`visible_to(user)`:

1. ناشناس یا غیرفعال -> هیچ ردیفی؛
2. superuser -> همه‌ی ردیف‌ها؛
3. در غیر این صورت، برای هر کدام از نقش‌های تعریف‌شده‌اش، scope آن نقش:
   * `scope_for_<role>(user)`، اگر queryset آن را تعریف کرده باشد؛
   * وگرنه همه‌ی ردیف‌ها، اگر نقش در `EVERY_ROW_ROLES` باشد؛
   * وگرنه هیچ؛
4. ردیف‌ها **اجتماع** آن scopeها هستند؛ اگر هیچ scopeی نباشد -> هیچ ردیفی.

یک hook یکی از این‌ها را برمی‌گرداند:

| مقدار برگشتی | یعنی |
|---|---|
| `Q(...)` | این ردیف‌ها - ارزان‌ترین برای ترکیب |
| `Q()` (خالی) | همه‌ی ردیف‌ها |
| یک queryset از همان مدل | این ردیف‌ها |
| `None` یا `self.none()` | هیچ |

با یک نقش، scope همان‌طور که هست اعمال می‌شود - queryset برگشتی بدون تغییر
برگردانده می‌شود. با چند نقش، `Q`ها با `OR` در یک `filter` ترکیب می‌شوند و
queryset برگشتی به‌صورت `Q(pk__in=queryset.values('pk'))` وارد می‌شود، تا
ترکیب هیچ‌وقت به محدودیت‌های `QuerySet.__or__` برنخورد. اگر یک نقش همه‌ی
ردیف‌ها را ببیند، جواب همه‌ی ردیف‌هاست. hookی که چیز دیگری برگرداند
`TypeError` می‌دهد.

یک `Q` که از یک رابطه‌ی چندتایی (to-many) عبور می‌کند، وقتی با دیگری ترکیب
شود ممکن است یک ردیف را تکراری برگرداند؛ مستندات این را می‌گوید و `pk__in` را
به‌عنوان راه‌حل نشان می‌دهد.

### ۵.۴ در یک policy

`has_role(user, *roles)` وقتی درست است که کاربر **هر کدام** از آن‌ها را داشته
باشد. `reaches_every_row(user)` جواب queryset درباره‌ی یک شیء است - superuser،
یا نقشی در `EVERY_ROW_ROLES` - برای policyای که تصمیم می‌گیرد آیا یک شیء
باید مال خود کاربر باشد یا نه. این تابع به *کدام ردیف‌ها* جواب می‌دهد، هرگز
به *چه کاری مجاز است*.

---

## ۶. پل DRF

`PolicyPermission` هر درخواست را به یک hook می‌رساند:

| ویو | hook |
|---|---|
| `list` | `can_list` |
| `retrieve` | `can_view` |
| `create` | `can_create` |
| `update`، `partial_update` | `can_edit` |
| `destroy` | `can_delete` |
| یک `@action` سفارشی | `custom_actions[name]`، وگرنه **رد** |
| یک `APIView` (بدون action) | متد HTTP: `GET`/`HEAD`/`OPTIONS` -> `can_list`، `POST` -> `can_create`، `PUT`/`PATCH` -> `can_edit`، `DELETE` -> `can_delete` |

در سطح شیء همین جدول اعمال می‌شود و خود شیء به hook داده می‌شود؛ action
سفارشی‌ای که map نشده، آنجا هم رد می‌شود.

`ScopedModelViewSet` و `ScopedReadOnlyViewSet` همان ویوست‌های خود DRF هستند
که `ScopedQuerySetMixin` رویشان اعمال شده. نسخه‌ی فقط‌خواندنی از mixinهای
خواندن ساخته شده، نه با کم کردن از `ModelViewSet`، تا DRF مسیرهای نوشتنی‌ای را
که هرگز سرویس نمی‌دهد منتشر نکند.

---

## ۷. تنظیمات

همه زیر یک دیکشنری به اسم `CLEARANCE`.

| کلید | پیش‌فرض | معنی |
|---|---|---|
| `ROLES` | اجباری | مسیر نقطه‌دار به یک `TextChoices`، یا لیستی از کدها. هر کد باید یک شناسه‌ی معتبر پایتون باشد، چون اسم یک hook را می‌سازد. |
| `ROLE_RESOLVER` | `'clearance.resolvers.AttributeResolver'` | مسیر نقطه‌دار به یک `RoleResolver` |
| `ROLE_ATTRIBUTE` | `'role'` | چیزی که `AttributeResolver` می‌خواند |
| `EVERY_ROW_ROLES` | `[]` | نقش‌هایی که همه‌ی ردیف‌های querysetی را که برایشان hook ندارد می‌بینند |
| `STARTING_PERMISSIONS` | `None` | مسیر نقطه‌دار به `{role: [app_label.codename, ...]}`، که `clearance_seed` می‌خواند |
| `ROLE_GROUP_NAME` | `'role:{role}'` | اسم گروهی که `clearance_seed` برای یک نقش می‌سازد |

---

## ۸. مدل‌ها (`clearance.roles`)

| مدل | فیلدها | قیدها |
|---|---|---|
| `RoleAssignment` | `user`، `role`، `assigned_by` (nullable)، `assigned_at` | یکتا روی `(user, role)`؛ `role` از میان `ROLES` |
| `RoleGroup` | `role`، `group` (`auth.Group`)، `linked_at` | یکتا روی `(role, group)`؛ `role` از میان `ROLES` |
| `PermissionRevocation` | `user`، `permission` (`auth.Permission`)، `revoked_by` (nullable)، `reason`، `revoked_at` | یکتا روی `(user, permission)` |
| `StartingPermissions` | `given_at`، `summary` (JSON) | حداکثر یک ردیف - بودنش یعنی «قبلاً داده شده» |

هر کلید خارجی به یک شخص، `settings.AUTH_USER_MODEL` است. `role` یک `CharField`
ساده است که در `clean()` و در سرویس‌ها با `ROLES` اعتبارسنجی می‌شود، نه با
لیست `choices` دیتابیس - تا اضافه کردن یک نقش فقط تغییر تنظیمات باشد، نه یک
migration.

### ۸.۱ مجوزهای اولیه، فقط یک بار

`clearance_seed`، که بعد از هر `migrate` اجرا می‌شود:

1. مطمئن می‌شود هر مجوز تعریف‌شده ردیفش را دارد؛
2. روی دیتابیسی که نه ردیف `StartingPermissions` دارد و نه ردیف `RoleGroup`،
   برای هر نقش از روی `STARTING_PERMISSIONS` یک گروه می‌سازد، وصلش می‌کند و
   ردیف `StartingPermissions` را می‌نویسد - **فقط یک بار**: از آن به بعد
   گروه‌ها مال دیتابیس‌اند و هیچ اجرای بعدی تغییرشان نمی‌دهد، حتی برای نقشی
   که کسی بی‌گروه رهایش کرده؛
3. مجوزهایی را که هیچ‌کس ندارد فهرست می‌کند - یعنی چیزهایی که یک نسخه‌ی جدید
   اضافه کرده - تا کسی تصمیم بگیرد به چه کسی داده شوند.

codenameی در جدول که وجود نداشته باشد، دستور را شکست می‌دهد و اسمش را
می‌گوید: مجوزی که بی‌صدا نادیده گرفته شود، یعنی نقشی که نمی‌تواند کارش را
بکند - و این با رد شدن یک آدم کشف می‌شود، نه با شکست خوردن یک deploy.

---

## ۹. بررسی‌های سیستمی (system checks)

| شناسه | چه زمانی |
|---|---|
| `clearance.E001` | `ROLES` وجود ندارد، import نمی‌شود، یا کدی دارد که شناسه‌ی معتبر نیست |
| `clearance.E002` | یک `ScopedQuerySet` متد `scope_for_<x>` را برای نقشی تعریف کرده که `ROLES` آن را ندارد - غلط تایپی‌ای که بی‌صدا رد می‌کرد |
| `clearance.E003` | ویوستی که با `PolicyPermission` محافظت شده، `@action`ای دارد که policyاش آن را map نکرده |
| `clearance.E004` | ویوستی که از `ScopedQuerySetMixin` استفاده می‌کند، querysetی تعریف کرده که `ScopedQuerySet` نیست |
| `clearance.E005` | `EVERY_ROW_ROLES` یا `STARTING_PERMISSIONS` نقشی را نام برده که `ROLES` آن را ندارد |
| `clearance.E006` | `clearance.roles` نصب است ولی `ClearanceBackend` در `AUTHENTICATION_BACKENDS` نیست - سلب مجوزها و گروه‌های نقش هیچ اثری نداشتند |
| `clearance.E007` | `ModelBackend` کنار `ClearanceBackend` در `AUTHENTICATION_BACKENDS` است - جنگو وقتی *هر کدام* از Backendها مجوزی بدهد آن را قبول می‌کند، پس همه‌ی مجوزهای سلب‌شده برمی‌گشتند |

E004 در زمان درخواست هم (با `ImproperlyConfigured`) بالا می‌آید، برای ویوستی
که پیکربندی URL به آن نمی‌رسد و check در نتیجه نمی‌تواند ببیندش.

---

## ۱۰. Signalها

در `clearance.signals`، هر کدام بعد از commit شدن تراکنش فرستاده می‌شود:

| signal | همراه با |
|---|---|
| `role_assigned` | `user`، `role`، `by` |
| `role_unassigned` | `user`، `role`، `by` |
| `permission_revoked` | `user`، `permission`، `by`، `reason` |
| `permission_restored` | `user`، `permission`، `by` |
| `starting_permissions_given` | `summary` - `{role: count}` |

---

## ۱۱. چه چیزی از DayarDarman می‌آید

| | DayarDarman | django-clearance |
|---|---|---|
| `build_permissions`، `DEFAULT_ACTIONS`، `RECORD_ACTIONS` | `apps/core/permissions/registry.py` | همان‌طور که هست |
| `PermissionRegistry`، `ResourcePermission` | همان فایل | همان‌طور که هست، به‌اضافه‌ی اعتبارسنجی `custom_actions` |
| `BasePolicy` | `apps/core/permissions/policies.py` | `_has` به `has` عمومی تبدیل می‌شود؛ `allows` و `authorize` اضافه می‌شوند؛ `has_role` یعنی هر کدام از چند نقش |
| `PolicyPermission` | `apps/core/permissions/drf.py` | همان‌طور که هست |
| `ScopedQuerySet.visible_to` | یک دیکشنری ثابت از شش نقش پزشکی | `scope_for_<role>` با اسم پیدا می‌شود، برای هر نقش تعریف‌شده؛ اجتماع بین نقش‌ها؛ `Q` یا queryset |
| `reaches_every_row` | `Role.every_row_roles()` | `EVERY_ROW_ROLES` |
| `Role` | یک `TextChoices` در `apps/core/enums.py` | مال خود پروژه، که در `ROLES` نام برده می‌شود |
| `User.role` | یک ستون | هر resolverی؛ `RoleAssignment` برای چند نقش |
| `RoleAccessGroup` | `role` -> `AccessGroup` (با اسم‌های ترجمه‌شده) | `RoleGroup`: `role` -> `auth.Group` |
| `RevocableModelBackend` | گروه‌های نقش + گروه‌های خود شخص - سلب‌ها | `ClearanceBackend`، همان قاعده روی چند نقش |
| `seed_roles`، `ROLE_PERMISSIONS` | «یک بار» با یک ردیف audit ثبت می‌شود | `clearance_seed`، «یک بار» با یک ردیف `StartingPermissions` ثبت می‌شود |
| ویوست‌های پایه | همراه با قالب پاسخ و صفحه‌بندی | فقط mixin محدودسازی |
| ردیف‌های audit | `AuditService` | signalها |
| scopeهای پزشکی، محتوای `ROLE_PERMISSIONS` | پروژه | در پروژه می‌مانند |

---

## ۱۲. سازگاری

| | پشتیبانی | تست در CI |
|---|---|---|
| Python | 3.11 تا 3.14 | همه‌شان |
| Django | 5.2 LTS، 6.0، 6.1 | هر کدام با همه‌ی نسخه‌های پایتونی که پشتیبانی می‌کند |
| Django REST framework | 3.16 و بالاتر، اختیاری | آخرین نسخه، روی همه‌ی نسخه‌های جنگو |
| دیتابیس | هر چیزی که جنگو پشتیبانی می‌کند | PostgreSQL و SQLite |

پشتیبانی از هر نسخه‌ی جنگو از `.0` آن شروع می‌شود و وقتی خود جنگو کنارش
بگذارد، کنار گذاشته می‌شود.

---

## ۱۳. قراردادهای این ریپو

* **کد فقط به انگلیسی** - سورس، کامنت‌ها، docstringها، تست‌ها. هر پیامی که
  آدم‌ها می‌خوانند با `gettext` علامت‌گذاری می‌شود؛ فارسی در
  `src/clearance/locale/fa/LC_MESSAGES/` است، compile‌شده و commit‌شده. CI هر
  کاراکتر غیر ASCII را در `src/` یا `tests/`، بیرون از `locale/`، رد می‌کند.
* **مستندات به انگلیسی و فارسی.** هر سند به انگلیسی نوشته و کنارش ترجمه
  می‌شود - `design.md` و `design.fa.md`، `README.md` و `README.fa.md` - و
  تغییر در یکی، در همان pull request روی دیگری هم اعمال می‌شود. کد در سند
  فارسی دقیقاً مثل سند انگلیسی می‌ماند.
* **docstring هر ماژول می‌گوید چرا وجود دارد**، و هر قاعده می‌گوید بدون آن
  چه چیزی خراب می‌شد.
* **اسم تست‌ها از رفتاری است که نگه می‌دارند** -
  `test_an_unmapped_action_is_refused.py`، نه `test_drf.py`.
* **هر ادعایی درباره‌ی هزینه، تست می‌شود** با `django_assert_num_queries`.
* **ruff** برای lint و قالب‌بندی؛ **mypy** همراه `django-stubs` روی `src/`.
* **هر مرحله یک pull request**، که قبل از شروع مرحله‌ی بعد بررسی و merge
  می‌شود.

---

## ۱۴. مرحله‌ها تا 0.1

هر کدام یک pull request است.

| مرحله | تحویل |
|---|---|
| 0 | همین سند |
| 1 | اسکلت: `pyproject.toml` (hatchling، ساختار `src/`، وابستگی اختیاری `drf`)، پروژه‌ی تست، pytest، ruff، mypy، nox، و GitHub Actions که ماتریس تست را اجرا می‌کند - بدون هیچ قابلیتی |
| 2 | `permissions`، `registry`، `policies`، با تست‌هایشان |
| 3 | `resolvers`، `querysets`، `views` و system checkهای هسته، با تست‌ها و شمارش کوئری‌هایشان |
| 4 | `drf`: پل، ویوست‌ها و checkهایشان |
| 5 | `roles`: مدل‌ها و migrationها، Backend، resolver، سرویس‌ها، `clearance_seed`، signalها، پنل ادمین |
| 6 | مستندات: README با شروع پنج‌دقیقه‌ای، سایت مستندات، یک پروژه‌ی نمونه؛ کاتالوگ فارسی |
| 7 | استفاده در iranbobco؛ رفع هر چیزی که آنجا معلوم شود؛ تگ `0.1.0`، public کردن ریپو، انتشار در PyPI |

## ۱۵. بعد از 0.1

برای 0.2 برنامه‌ریزی شده: بخش‌هایی از DayarDarman که مجوزها را *مدیریت*
می‌کنند، نه اینکه فقط بررسی‌شان کنند:

* **قواعد ایمنی تغییر مجوز**: هیچ‌کس مجوزهای خودش را تغییر نمی‌دهد؛ هیچ‌کس
  چیزی را که خودش ندارد به کسی نمی‌دهد؛ تغییری که باعث شود جز superuser هیچ‌کس
  نتواند مجوزها را مدیریت کند رد می‌شود؛ هر مجوز فقط به نقشی داده می‌شود که
  برایش کاری انجام می‌دهد (`ONLY_FOR`)؛ تغییر نقش، چیزهایی را که در نقش جدید
  کاری انجام نمی‌دهند می‌گیرد.
* **مدیریت گروه‌ها از طریق یک سرویس**، و پنل ادمین که از همان سرویس عبور
  می‌کند، نه از کنارش.
* **توصیف مجوزها برای فرانت‌اند** - هر کدام به‌صورت یک بخش، یک action، و
  اینکه می‌خواند یا می‌نویسد - و endpointهای REST برای صفحه‌ی مجوزها و برای
  «من چه کارهایی می‌توانم بکنم».
* **اسم گروه‌ها به چند زبان.**

---

## ۱۶. تصمیم‌ها

این‌ها را صاحب پروژه هنگام بررسی این سند گرفته است.

1. **هر import اسم ماژولش را می‌آورد** - `from clearance.policies import
   BasePolicy`، هرگز `from clearance import BasePolicy`.
2. **صاحب حق کپی در لایسنس** amir mohammad kashanchian است.
3. **قدیمی‌ترین نسخه‌ی پایتون 3.11 است.** پشتیبانی 3.10 در اکتبر ۲۰۲۶ تمام
   شد، و خود جنگو ۶ به 3.12 نیاز دارد.
4. **resolver پیش‌فرض `AttributeResolver` است که `user.role` را می‌خواند**،
   یعنی همان شکلی که بیشتر پروژه‌ها از قبل دارند. پروژه‌ای که بدون ستون
   مخصوص خودش چند نقش می‌خواهد، به `AssignmentResolver` تغییر می‌دهد.
