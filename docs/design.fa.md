# django-clearance - طراحی

> **وضعیت: ویرایش دوم، تأییدشده.** ویرایش اول نقش‌ها را در مرکز گذاشته
> بود. صاحب پروژه در بررسی، ترتیب را برعکس کرد: **اول بسته‌های دسترسی، بعد
> scope ردیف‌ها و فیلدهای محافظت‌شده، و در آخر نقش‌ها، به‌عنوان یک محدودکننده‌ی
> اختیاری.** مرحله‌های ۰ تا ۳ روی ویرایش اول ساخته شده‌اند؛ چیزی که این ویرایش
> در آن‌ها عوض می‌کند در بخش ۱۹ آمده است.
>
> انگلیسی: [`design.md`](design.md). این سند ترجمه‌ی آن است و هر دو با هم
> به‌روز می‌شوند.

**django-clearance** - کنترل دسترسی مبتنی بر نقش، سیاست (policy) و سطح ردیف
برای جنگو. پیش‌فرض: رد.

## چهار لایه

| | لایه | سؤال | جواب‌دهنده |
|---|---|---|---|
| ۱ | **بسته‌های دسترسی** | این شخص چه کاری می‌تواند بکند؟ | مجوزها، از طریق **بسته‌های** اسم‌دار که به آدم‌ها داده می‌شوند - هر کس چندتا |
| ۲ | **scope ردیف** | روی کدام ردیف‌ها؟ | یک **scope** که برای هر مجوز داخل بسته انتخاب می‌شود: همه‌ی ردیف‌ها، مال خودش، مال شعبه‌اش |
| ۳ | **فیلدهای محافظت‌شده** | کدام فیلدهای یک ردیف؟ | یک مجوز مخصوص برای **دیدن** و یکی برای **ویرایش** هر فیلد حساس |
| ۴ | **نقش‌ها** (اختیاری) | این نوع آدم چه کاری را هرگز نباید بکند؟ | یک **سقف** که هیچ بسته‌ای از آن رد نمی‌شود، و بسته‌هایی که نقش **از اول** می‌دهد |

یک پروژه سه لایه‌ی اول را بدون تعریف حتی یک نقش استفاده می‌کند. نقش‌ها برای
پروژه‌ای است که انواع مختلف آدم دارد - مشتری، کارشناس - و تضمین می‌خواهد که
یک مشتری هرگز قدرت یک کارشناس را پیدا نکند، هر اشتباهی که مدیر سایت بکند.

بالای این لایه‌ها، برای هر منبع یک **policy** هست؛ تنها جایی که هر ویو، سرویس
و دستور می‌پرسد «آیا این شخص می‌تواند این کار را روی این شیء بکند؟». policy از
روی لایه‌ها جواب می‌دهد و قانون‌هایی را اضافه می‌کند که هیچ مجوزی نمی‌تواند
بگوید - «هیچ‌کس وام خودش را تأیید نمی‌کند».

نگه داشتن scope ردیف‌ها در queryset، و نه در بررسی مجوز، سلیقه نیست: DRF متد
`has_object_permission` را فقط وقتی صدا می‌زند که ویو یک شیء را پیدا کرده
باشد، و ویوهای generic جنگو اصلاً چنین hookی ندارند. لیستی که فقط با بررسی
مجوز محافظت شده، همه‌ی ردیف‌های جدول را برمی‌گرداند - و هیچ خطایی هم نمی‌دهد،
و همین است که آن را خطرناک می‌کند.

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
   * actionی از ویو که هیچ policyای آن را map نکرده رد می‌شود؛
   * سقف یک نقش جلوی چیزی را که یک بسته می‌داد می‌گیرد.
2. **تنظیمات اشتباه سروصدا می‌کند.** هر چیزی که موقع بالا آمدن برنامه قابل
   بررسی است، یک system check جنگو است (`manage.py check` و هر بار
   `runserver`). پس در زمان توسعه و در CI شکست می‌خورد، نه به‌صورت یک 403 که
   کسی گزارشش کند - یا یک 200 که هیچ‌کس گزارشش نکند. چیزی که فقط با دیتابیس
   قابل بررسی است، دستور مدیریتی‌ای را که به آن برمی‌خورد شکست می‌دهد. بخش ۱۴
   را ببینید.
3. **جدول‌های خود جنگو محل ذخیره‌اند.** مجوزها ردیف‌های `auth_permission`
   هستند که `migrate` می‌سازد؛ یک بسته یک `auth.Group` است؛ بسته‌های هر شخص
   همان `user.groups` است. پس `user.has_perm()`، `PermissionRequiredMixin`،
   `{{ perms }}` و پنل ادمین همچنان کار می‌کنند و هیچ چیزی همگام‌سازی نمی‌شود.
4. **پرسیدن ارزان است.** فهمیدن اینکه یک شخص چه مجوزهایی دارد، همان کوئری‌هایی
   را می‌زند که Backend خود جنگو می‌زند؛ scopeهای او یک کوئری در هر درخواست
   می‌زنند که یک بار خوانده می‌شود؛ و لیستی که با آن‌ها محدود شده همچنان یک
   کوئری است. تست‌ها این‌ها را می‌شمارند.
5. **همه‌ی لایه‌ها اختیاری‌اند.** `'clearance'` در `INSTALLED_APPS` لایه‌های ۱
   تا ۳ را دارد، و هر کدام فقط جایی استفاده می‌شود که پروژه بخواهد: بسته‌ها
   وقتی پروژه یکی بسازد - مجوزها را می‌شود مستقیم به آدم‌ها داد؛ scope ردیف
   فقط روی مدلی که manager آن `ScopedQuerySet` باشد - بقیه‌ی مدل‌ها همان‌طور
   کار می‌کنند که جنگو همیشه کار کرده؛ فیلدهای محافظت‌شده فقط روی مدلی که
   فهرستشان را بدهد. DRF، نقش‌ها و ترجمه‌ها را فقط پروژه‌ای اضافه می‌کند که
   آن‌ها را می‌خواهد. تنها چیز اجباری `ClearanceBackend` است، که بدون آن سلب‌ها
   و scopeها بی‌صدا هیچ اثری نداشتند (E006).
6. **درباره‌ی بقیه‌ی چیزها نظری ندارد.** قالب پاسخ، قالب خطاها، محل ذخیره‌ی
   audit و مدل کاربر مال پروژه هستند. کتابخانه signal می‌فرستد و خطاهای خود
   جنگو و DRF را بالا می‌اندازد.

---

## ۲. قابلیت‌ها (نسخه‌ی 0.1)

چیزهایی که README فهرست خواهد کرد.

* **بسته‌های دسترسی.** برای مجموعه‌ای از مجوزها اسم بگذارید و آن را به هر
  کسی بدهید؛ هر شخص می‌تواند چندتا داشته باشد. نقش لازم نیست.
* **مجوزها در خود مدل تعریف می‌شوند.** `build_permissions('order',
  'orders')` در `Meta.permissions`؛ `migrate` آن‌ها را می‌سازد.
* **scope ردیف، برای هر مجوز.** یک بسته می‌تواند `order_view` را روی همه‌ی
  سفارش‌ها بدهد و `order_edit` را فقط روی سفارش‌های شعبه‌ی خود شخص. برنامه‌نویس
  یک بار scopeها را در queryset نام‌گذاری می‌کند؛ مدیر سایت برای هر مجوز، در
  پنل ادمین یکی را انتخاب می‌کند.
* **فیلدهای محافظت‌شده.** `protected_fields=('price',)` مجوزهای
  `order_view_price` و `order_edit_price` را می‌سازد. بدون اولی قیمت نشان داده
  نمی‌شود - در API، در فرم‌ها، در پنل ادمین؛ بدون دومی نمی‌شود تغییرش داد.
* **گرفتن یک مجوز از یک نفر**، از هر بسته‌ای که آن را داده باشد.
* **policy با hookهای سطح شیء** که scope ردیف‌ها را رعایت می‌کنند:
  `allows(user, 'edit', order)` برای سفارشی که بیرون از scope ویرایش شخص است
  `False` است.
* **هم با DRF و هم بدون آن.** mixinهایی برای ویوها و فرم‌های generic جنگو،
  یک decorator برای ویوهای تابعی، و کلاس مجوز، ویوست‌ها و serializer مربوط
  به DRF که از همان policy ساخته می‌شوند.
* **در پنل ادمین.** هر مجوز همراه با کسانی که آن را دارند؛ ساختن بسته با
  انتخاب یک scope برای هر مجوز؛ بسته‌ها، مجوزهای مستقیم و سلب‌های هر شخص در
  صفحه‌ی خودش.
* **نقش‌ها، وقتی پروژه آن‌ها را دارد.** یک سقف برای هر نقش، نوشته‌شده در کد،
  که هیچ بسته یا مجوز مستقیمی از آن رد نمی‌شود؛ بسته‌هایی که نقش از اول
  می‌دهد؛ چند نقش برای هر شخص، هر جا که پروژه نگهشان دارد.
* **اسم هر مجوز و هر بسته به هر زبانی** که مدیر سایت بخواهد، از داخل پنل
  ادمین.
* **signal برای هر تغییر**، برای audit مخصوص خود پروژه.
* **ترجمه‌شده و دارای type.** انگلیسی و فارسی همراه بسته می‌آیند؛ `py.typed`
  هم همین‌طور.

---

## ۳. کل مدل در یک تصویر

```
held     = direct grants + their bundles' permissions + their roles' starting bundles' permissions
         - what was taken away from them
allowed  = held, within the ceilings of their roles            (only when roles are used)

rows     = the union of the scopes of every grant of that permission that reaches them
fields   = a protected field needs <codename>_view_<field> to be read, _edit_ to be written
```

یعنی:

* **مجوزهای شخص** = مجوزهای مستقیم + مجوزهای بسته‌هایش + مجوزهای بسته‌های اولیه‌ی
  نقش‌هایش - چیزهایی که از او گرفته شده.
* **مجوزهای مجاز** = همان، محدود به سقف نقش‌هایش (فقط وقتی نقش استفاده شود).
* **ردیف‌ها** = اجتماع scopeهای هر بسته یا مجوزی که آن مجوز را به او می‌دهد.
* **فیلدها** = فیلد محافظت‌شده برای دیدن `<codename>_view_<field>` و برای
  ویرایش `_edit_` می‌خواهد.

superuser همه‌ی مجوزها را دارد، به همه‌ی ردیف‌ها می‌رسد و همه‌ی فیلدها را
می‌بیند، مثل خود جنگو.

---

## ۴. ساختار بسته

```
src/clearance/
    __init__.py            empty
    apps.py                ClearanceConfig - registers the system checks
    conf.py                reading and validating the CLEARANCE setting
    protocols.py           User - the three things the library asks of a person
    permissions.py         build_permissions: actions and protected fields
    registry.py            one policy per resource
    policies.py            BasePolicy, SignedInReadPolicy
    models.py              ScopeGrant, PermissionRevocation
    backends.py            ClearanceBackend
    grants.py              what a person holds, and with which scopes - read once per request
    services.py            AccessService: bundles, grants, scopes, revocations - every change, with signals
    querysets.py           ScopedQuerySet: named scopes, visible_to(user, action)
    fields.py              readable_fields(), writable_fields()
    forms.py               ProtectedFieldsFormMixin
    views.py               ScopedQuerySetMixin, PolicyRequiredMixin, ProtectedFieldsViewMixin
    decorators.py          policy_required
    labels.py              label_of() - a permission's or bundle's name, in the reader's language
    admin.py               the permission page; the bundle page, a scope per permission; the user page
    checks.py              the system checks
    signals.py             every signal the library sends
    migrations/
    locale/fa/LC_MESSAGES/

    drf/                   pip install django-clearance[drf]
        permissions.py     PolicyPermission
        viewsets.py        ScopedModelViewSet, ScopedReadOnlyViewSet
        serializers.py     ProtectedFieldsSerializerMixin
        checks.py

    roles/                 INSTALLED_APPS += ['clearance.roles']
        apps.py            label 'clearance_roles'
        models.py          RoleAssignment, RoleBundle, StartingBundles
        resolvers.py       RoleResolver, AttributeResolver, AssignmentResolver, roles_of()
        ceilings.py        a role's ceiling, from the code
        seeding.py         the starting bundles, once
        admin.py
        management/commands/clearance_seed.py

    translations/          INSTALLED_APPS += ['clearance.translations']
        models.py          PermissionTranslation, BundleTranslation
        sources.py         the label source that reads them
        admin.py
```

همه‌ی فایل‌های `__init__.py` خالی‌اند و هر چیزی از همان ماژولی import می‌شود
که تعریفش کرده. هسته هیچ چیزی از `drf`، `roles` یا `translations` import
نمی‌کند؛ هر کدام از طریق hookی که هسته ارائه می‌دهد به آن وصل می‌شود.

---

## ۵. API، با یک مثال

یک فروشگاه: سفارش‌هایی که مشتری‌ها در یکی از چند شعبه ثبت می‌کنند، و کارمندهایی
که آن‌ها را مدیریت می‌کنند و فقط بعضی‌شان اجازه‌ی دیدن قیمت را دارند.

### ۵.۱ تنظیمات

```python
INSTALLED_APPS += ['clearance']

# Replaces django.contrib.auth.backends.ModelBackend - see E006 and E007.
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']
```

برای لایه‌های ۱ تا ۳ چیز دیگری لازم نیست: نه تنظیم `CLEARANCE`، نه نقش.

### ۵.۲ مدل مجوزها و فیلدهای محافظت‌شده‌اش را تعریف می‌کند

```python
from clearance.permissions import build_permissions

class Order(models.Model):
    customer = models.ForeignKey(Customer, ...)
    branch = models.ForeignKey(Branch, ...)
    status = models.CharField(...)
    price = models.DecimalField(...)

    objects = OrderQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        permissions = build_permissions('order', _('orders'), protected_fields=('price',))
```

`migrate` این مجوزها را می‌سازد: `order_view`، `order_create`، `order_edit`،
`order_delete`، `order_view_price` و `order_edit_price`.

### ۵.۳ queryset اسم scopeهایش را می‌گوید

```python
from clearance.querysets import ScopedQuerySet

class OrderQuerySet(ScopedQuerySet):
    default_scope = 'all'      # optional: what a grant with no scope reaches
    scopes = {
        'own': _('Their own orders'),
        'branch': _("Their branch's orders"),
    }

    def scope_own(self, user):
        return Q(customer__user=user)

    def scope_branch(self, user):
        return Q(branch__staff=user)
```

`all` - «همه‌ی ردیف‌ها» - همیشه هست و متد لازم ندارد.

### ۵.۴ بسته‌ها، در پنل ادمین یا در کد

مدیر سایت آن‌ها را در صفحه‌ی بسته‌ها می‌سازد و کنار هر مجوز یک scope انتخاب
می‌کند. همین کار در کد:

```python
from clearance.services import AccessService

access = AccessService(actor=request.user)

branch_managers = access.create_bundle(
    'Branch managers',
    grants={'shop.order_view': 'branch', 'shop.order_edit': 'branch'},
)
accountants = access.create_bundle(
    'Accountants',
    grants={'shop.order_view': 'all', 'shop.order_view_price': None},
)

access.give_bundle(person, branch_managers)
access.give_bundle(person, accountants)
access.revoke(person, 'shop.order_edit', reason='Under review')
```

حالا `person` همه‌ی سفارش‌ها و قیمتشان را می‌بیند و هیچ چیزی را ویرایش
نمی‌کند - چون از او گرفته شد - و هیچ کس دیگری که «Branch managers» را دارد
چیزی از دست نداد.

### ۵.۵ policy

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class OrderPolicy(BasePolicy):
    app_label = 'shop'
    codename = 'order'

order_access = registry.register(OrderPolicy)

order_access.policy.allows(user, 'edit', order)    # order_edit, and the order within their edit scope
order_access.policy.authorize(user, 'edit', order)  # or Django's PermissionDenied
```

### ۵.۶ ویوها، فرم‌ها و API

```python
from clearance.views import PolicyRequiredMixin, ProtectedFieldsViewMixin, ScopedQuerySetMixin

class OrderListView(PolicyRequiredMixin, ScopedQuerySetMixin, ListView):
    policy = order_access.policy          # the rows: visible_to(user, 'view')
    queryset = Order.objects.all()

class OrderUpdateView(
    PolicyRequiredMixin, ScopedQuerySetMixin, ProtectedFieldsViewMixin, UpdateView
):
    policy = order_access.policy          # the rows: visible_to(user, 'edit')
    queryset = Order.objects.all()
    fields = ('status', 'price')          # price leaves the form without order_edit_price
```

```python
@policy_required(order_access.policy, 'create')
def place_order(request):
    ...
```

```python
from clearance.drf.serializers import ProtectedFieldsSerializerMixin

class OrderSerializer(ProtectedFieldsSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('id', 'status', 'price')   # price is left out without order_view_price
```

### ۵.۷ بیرون از ویو

```python
Order.objects.visible_to(user, 'edit')       # the orders they may edit
readable_fields(user, Order)                 # {'id', 'customer', 'branch', 'status'}
writable_fields(user, Order)
```

### ۵.۸ نقش‌ها، برای پروژه‌ای که آن‌ها را دارد

```python
INSTALLED_APPS += ['clearance', 'clearance.roles']

CLEARANCE = {
    'ROLES': 'accounts.roles.Role',
    'ROLE_CEILINGS': 'config.access.CEILINGS',
    'STARTING_BUNDLES': 'config.access.STARTING_BUNDLES',
}
```

```python
# config/access.py
CEILINGS = {
    'customer': ['shop.order_view', 'shop.order_create'],   # a customer can never hold more
}

STARTING_BUNDLES = {
    'customer': {'Customers': {'shop.order_view': 'own', 'shop.order_create': None}},
}
```

### ۵.۹ اسم‌ها به هر زبانی

```python
from clearance.labels import label_of

label_of(permission)                 # in the language of the request
label_of(bundle, language='fa')
```

---

## ۶. لایه‌ی ۱: بسته‌های دسترسی

یک **بسته** یک `Group` جنگو است: یک اسم و مجوزهایی که دارد. بسته‌های هر شخص
همان `user.groups` است؛ پس هر شخص می‌تواند چندتا داشته باشد، و دادن بسته همان
کاری است که جنگو همیشه انجام می‌داده. چیزهایی که کتابخانه اضافه می‌کند:

* **یک scope کنار هر مجوز در یک بسته** (لایه‌ی ۲)؛
* **سلب مجوز**: گرفتن یک مجوز از یک نفر، از هر بسته‌ای که آن را داده باشد،
  بدون اینکه برایش بسته‌ی جداگانه ساخته شود. سلب از چیزی که بسته‌ها می‌دهند کم
  می‌کند؛ مجوزی که مستقیم به شخص داده شده، سلب نمی‌شود بلکه حذف می‌شود؛
* **اسم به هر زبانی** (`clearance.translations`)؛
* **یک سرویس** برای هر تغییر - `AccessService` - تا پنل ادمین، یک API و یک
  دستور مدیریتی همه به یک شکل دسترسی را تغییر دهند و همان signalها را
  بفرستند.

`ClearanceBackend` جای `ModelBackend` را می‌گیرد. مجوزهای هر شخص را با همان
کوئری‌هایی که `ModelBackend` می‌زند حساب می‌کند - سلب‌ها داخل همان کوئری کم
می‌شوند - و cache جنگو را نگه می‌دارد.

---

## ۷. لایه‌ی ۲: scope ردیف

### ۷.۱ scopeهایی که یک مدل ارائه می‌دهد

مدلی که با یک `ScopedQuerySet` مدیریت می‌شود، scopeهایی را ارائه می‌دهد که
queryset آن در `scopes` تعریف کرده - یک کد و یک برچسب برای نشان دادن به مدیر
سایت - و هر کدام یک متد `scope_<code>(user)` دارد. `all` همیشه هست و یعنی همه‌ی
ردیف‌ها. یک hook یکی از این‌ها را برمی‌گرداند:

| جواب | یعنی |
|---|---|
| `Q(...)` | این ردیف‌ها - ارزان‌ترین برای ترکیب |
| `Q()` | همه‌ی ردیف‌ها |
| یک queryset از همان مدل | این ردیف‌ها |
| `None` یا `self.none()` | هیچ |

مدلی که با یک `QuerySet` معمولی مدیریت می‌شود ردیفی برای محدود کردن ندارد:
مجوزهایش همان‌طور کار می‌کنند که جنگو همیشه کار کرده.

### ۷.۲ یک scope برای هر مجوز

`ScopeGrant` ثبت می‌کند که یک مجوز با کدام scope داده شده: در یک بسته، یا
مستقیم به یک نفر. یک بسته می‌تواند `order_view` را با `all` و `order_edit` را
با `branch` بدهد.

مجوزی که **بدون** scope داده شده، به همان چیزی می‌رسد که `default_scope`
queryset نام برده. querysetی که هیچ‌کدام را نام نبرد - حالت پیش‌فرض - به چنین
مجوزی **هیچ ردیفی** نمی‌دهد: جواب امن برای مجوزی که کسی کاملش نکرده، و
`clearance_check` همه‌شان را فهرست می‌کند. انتخاب بین راحتی و سخت‌گیرانه‌ترین
جواب با برنامه‌نویس است، یک بار برای هر مدل:

| `default_scope` | مجوز بدون scope به کجا می‌رسد | مدیر سایت |
|---|---|---|
| نوشته نشده | هیچ ردیفی | برای همه‌ی مجوزهای مدل یک scope انتخاب می‌کند |
| `'all'` | همه‌ی ردیف‌ها | فقط برای محدود کردن یک مجوز scope انتخاب می‌کند |
| هر scopeی که تعریف کرده | ردیف‌های همان scope | فقط برای عوض کردنش scope انتخاب می‌کند |

`default_scope`ی که queryset تعریفش نکرده، خطای E002 است.

### ۷.۳ یک شخص به کدام ردیف‌ها می‌رسد

`Model.objects.visible_to(user, action='view')`:

1. وارد نشده، یا غیرفعال -> هیچ ردیفی؛ superuser -> همه‌ی ردیف‌ها؛
2. شخص مجوز آن action را ندارد - هرگز نداشته، از او گرفته شده، یا سقف یک نقش
   جلویش را گرفته -> هیچ ردیفی؛
3. وگرنه، scopeهای هر مجوزی از آن نوع که به او می‌رسد - مستقیم، از طریق
   بسته‌هایش، از طریق بسته‌های اولیه‌ی نقش‌هایش - با OR در **یک** filter ترکیب
   می‌شوند؛ `all` آن را همه‌ی ردیف‌ها می‌کند.

مجوزهای شخص یک بار در هر درخواست، با یک کوئری، خوانده می‌شوند و روی شیء کاربر
نگه داشته می‌شوند، همان‌طور که جنگو مجوزهایش را نگه می‌دارد. بعد خود لیست یک
کوئری است، هر قدر هم scope باشد.

### ۷.۴ یک شیء

hookهای policy به scopeها احترام می‌گذارند: وقتی شیئی از یک مدل scoped به
آن‌ها داده شود، `can_edit(user, obj)` هم `order_edit` را می‌خواهد **و** هم اینکه
شیء داخل scope `edit` شخص باشد. یک ویو شیئش را از قبل از میان
`visible_to(user, action)` پیدا می‌کند، پس آنجا hook هیچ کوئری اضافه‌ای
نمی‌زند؛ وقتی از یک سرویس پرسیده شود، یک `exists()` هزینه دارد.

---

## ۸. لایه‌ی ۳: فیلدهای محافظت‌شده

### ۸.۱ تعریفشان

`build_permissions(..., protected_fields=('price',))` برای هر فیلد
`<codename>_view_<field>` و `<codename>_edit_<field>` را می‌سازد. فیلدهایی که
در فهرست نیستند با همان `view` و `edit` خود ردیف خوانده و نوشته می‌شوند. فیلد
محافظت‌شده باید یکی از فیلدهای مدل باشد (E012).

### ۸.۲ دو قانون

* **خواندن:** بدون `view_<field>`، فیلد **حذف می‌شود** - کلیدش در جواب نیست،
  نه اینکه `null` باشد - تا هیچ چیزی وجودش را نگوید.
* **نوشتن:** بدون `edit_<field>`، فیلد در فرم نشان داده نمی‌شود، و مقداری که
  برایش به یک API فرستاده شود **رد می‌شود** و اسم فیلد گفته می‌شود. نادیده
  گرفتنش باعث می‌شد فرستنده فکر کند تغییر کرده.

### ۸.۳ همه‌ی درها

| کجا | چطور |
|---|---|
| یک فرم جنگو | `ProtectedFieldsFormMixin` چیزی را که نمی‌شود خواند حذف می‌کند، و چیزی را که خوانده می‌شود ولی نوشته نمی‌شود فقط‌خواندنی نشان می‌دهد |
| یک ویوی جنگو | `ProtectedFieldsViewMixin` فرم را همین‌طور می‌سازد |
| پنل ادمین | `ProtectedFieldsAdminMixin` به همین شکل پنهان یا قفل می‌کند |
| یک serializer در DRF | `ProtectedFieldsSerializerMixin` به همین شکل حذف و رد می‌کند |
| یک تمپلیت | `{% if perms.shop.order_view_price %}` |
| کد | `readable_fields(user, Order)`، `writable_fields(user, Order)` |

کتابخانه درهایی را نگهبانی می‌کند که خودش ارائه می‌دهد. کدی که خودش
`Order.objects.values('price')` را می‌خواند، نگهبانی‌اش با خود پروژه است؛
مستندات این را می‌گوید.

در 0.1 مجوزهای یک فیلد مال شخص است، نه مال ردیف: scope نمی‌گیرند (بخش ۲۰).

---

## ۹. لایه‌ی ۴: نقش‌ها (اختیاری)

`clearance.roles` برای پروژه‌ای است که انواع مختلف آدم دارد.

* **نقش‌های هر شخص** را یک resolver از هر جایی که پروژه نگهشان داشته می‌خواند:
  `AttributeResolver` ستون `user.role` را می‌خواند (یک کد، یا یک لیست)؛
  `AssignmentResolver` ردیف‌های `RoleAssignment` خود اپ را می‌خواند؛ و پروژه
  برای هر چیز دیگری - `is_staff`، گروه‌های جنگو - resolver خودش را می‌نویسد. هر
  شخص می‌تواند چند نقش داشته باشد. نقشی که پروژه تعریف نکرده هیچ اثری ندارد.
* **یک سقف**، در کد: `ROLE_CEILINGS` هر نقش را به مجوزهایی وصل می‌کند که هرگز
  می‌تواند داشته باشد (`'shop.*'` یعنی همه‌ی مجوزهای یک اپ). چیزی که به شخص
  اجازه داده می‌شود، همان چیزی است که دارد، محدود به اجتماع سقف‌های نقش‌هایش.
  نقشی که سقف ندارد با سقف محدود نمی‌شود. سقف در Backend و بعد از همه چیز
  اعمال می‌شود، پس نه بسته، نه مجوز مستقیم و نه بسته‌ی اولیه از آن رد نمی‌شود.
  عمداً در کد است، نه یک تنظیم در پنل ادمین: سقف تضمینی در برابر اشتباه مدیر
  سایت است، پس مدیر سایت نباید بتواند آن را بازتر کند.
* **بسته‌های اولیه**: `RoleBundle` یک نقش را به بسته‌هایی وصل می‌کند که هر کسی
  با آن نقش دارد؛ `clearance_seed` آن‌ها را یک بار، از روی `STARTING_BUNDLES`
  و روی یک دیتابیس تازه می‌سازد، و دیگر هرگز.
* **در یک policy**، `has_role(user, *roles)` جواب می‌دهد یک کار کار چه کسی
  است - «فقط کارشناس تأیید می‌کند» - چیزی که یک مجوز نمی‌تواند بگوید.

---

## ۱۰. از ویو تا policy

### ۱۰.۱ DRF

`PolicyPermission` این‌ها را به hookها می‌رساند: `list`/`retrieve` به
`can_list`/`can_view`، `create` به `can_create`، `update`/`partial_update` به
`can_edit`، `destroy` به `can_delete`، یک `@action` سفارشی به
`custom_actions[name]` - وگرنه **ردش می‌کند** - و یک `APIView` بر اساس متد
HTTP. سطح شیء هم همین جدول است، با خود شیء. ویوست‌های scoped، queryset خود را
با scope همان action محدود می‌کنند.

### ۱۰.۲ ویوهای جنگو

`PolicyRequiredMixin` نوع کار را از نوع ویو می‌خواند - `ListView` یعنی `list`،
`DetailView` یعنی `view`، `CreateView` یعنی `create`، `UpdateView` یعنی
`edit`، `DeleteView` یعنی `delete` - یا از `policy_action` می‌گیرد؛ ویویی که
نشود نوع کار را از آن خواند `ImproperlyConfigured` است و هرگز اجازه نمی‌دهد.
هر ویو اول در `dispatch` بدون شیء می‌پرسد؛ ویویی که شیء دارد، بعد از اینکه
`get_object()` آن را از میان `visible_to(user, action)` پیدا کرد، دوباره با
شیء می‌پرسد. رد شدن همان رفتار خود جنگو است: صفحه‌ی ورود برای کسی که وارد
نشده، و 403 برای بقیه. `@policy_required(policy, action)` بررسی اول را برای
یک ویوی تابعی انجام می‌دهد.

---

## ۱۱. تنظیمات

همه زیر `CLEARANCE`؛ لایه‌های ۱ تا ۳ به هیچ‌کدام نیاز ندارند. کلیدی که
کتابخانه نمی‌شناسد رد می‌شود (E011).

| کلید | پیش‌فرض | معنی |
|---|---|---|
| `ROLES` | برای `clearance.roles` اجباری | یک `TextChoices`، یا لیستی از کدها |
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AttributeResolver'` | نقش‌های هر شخص از کجا خوانده شود |
| `ROLE_ATTRIBUTE` | `'role'` | چیزی که `AttributeResolver` می‌خواند |
| `ROLE_CEILINGS` | `None` | `{role: [permission or 'app_label.*', ...]}` |
| `STARTING_BUNDLES` | `None` | `{role: {bundle name: {permission: scope}}}`، که `clearance_seed` می‌خواند |

---

## ۱۲. مدل‌ها

| اپ | مدل | چه چیزی نگه می‌دارد |
|---|---|---|
| `clearance` | `ScopeGrant` | `group` یا `user` (دقیقاً یکی)، `permission`، `scope`؛ یکتا برای هر صاحب و مجوز |
| `clearance` | `PermissionRevocation` | `user`، `permission`، `revoked_by`، `reason`، `revoked_at`؛ یکتا برای هر شخص و مجوز |
| `clearance.roles` | `RoleAssignment` | `user`، `role`، `assigned_by`، `assigned_at` |
| `clearance.roles` | `RoleBundle` | `role`، `group` |
| `clearance.roles` | `StartingBundles` | حداکثر یک ردیف: بسته‌های اولیه داده شده‌اند |
| `clearance.translations` | `PermissionTranslation`، `BundleTranslation` | یک اسم و یک توضیح برای هر زبان در `LANGUAGES` |

هر کلید خارجی به یک شخص `settings.AUTH_USER_MODEL` است. نقش‌ها و زبان‌ها با
تنظیمات اعتبارسنجی می‌شوند، نه به‌صورت `choices` در دیتابیس، تا اضافه کردن
یکی‌شان migration نباشد.

---

## ۱۳. پنل ادمین

| صفحه | چه چیزی نشان می‌دهد |
|---|---|
| **مجوزها** (جدید، فقط‌خواندنی) | هر مجوز، اسمش به زبان خواننده، بسته‌هایی که آن را دارند و با کدام scope؛ با فیلتر بر اساس اپ و بسته - و با `clearance.roles` بر اساس نقش |
| **بسته‌ها** (صفحه‌ی گروه جنگو، گسترش‌یافته) | ساختن بسته با مجوزهایش، **با انتخاب یک scope کنار هر کدام** از میان scopeهایی که مدلش ارائه می‌دهد؛ با `clearance.roles`، نقش‌هایی که از اول آن را می‌دهند؛ با `clearance.translations`، اسمش به هر زبان |
| **صفحه‌ی کاربر** (مال خود پروژه) | بسته‌های شخص، مجوزهای مستقیمش همراه scopeهایشان، و چیزهایی که از او گرفته شده و دلیلش؛ با `clearance.roles`، نقش‌هایش |
| **صفحه‌ی مدل‌ها** | `ProtectedFieldsAdminMixin` روی هر `ModelAdmin` فیلدهای محافظت‌شده را پنهان یا قفل می‌کند |

هر صفحه از طریق `AccessService` می‌نویسد، پس پنل ادمین هرگز راه دور زدن
قانون‌ها نیست.

---

## ۱۴. بررسی‌های سیستمی (system checks)

| شناسه | چه زمانی |
|---|---|
| `clearance.E001` | `clearance.roles` نصب است و `ROLES` وجود ندارد یا معتبر نیست |
| `clearance.E002` | `scopes` یک `ScopedQuerySet` اسم scopeی را آورده که متد ندارد، یک متد `scope_<x>` در `scopes` نیست، یا `default_scope` آن نه `all` است و نه یک scope تعریف‌شده |
| `clearance.E003` | یک ویوست DRF که با policy محافظت شده، `@action`ای دارد که policy آن را map نکرده |
| `clearance.E004` | queryset یک ویوی scoped یک `ScopedQuerySet` نیست |
| `clearance.E005` | `ROLE_CEILINGS` یا `STARTING_BUNDLES` نقشی را نام برده که تعریف نشده |
| `clearance.E006` | `ClearanceBackend` در `AUTHENTICATION_BACKENDS` نیست - scopeها، سلب‌ها و سقف‌ها هیچ اثری نداشتند |
| `clearance.E007` | `ModelBackend` کنار `ClearanceBackend` است - جنگو وقتی *هر کدام* از Backendها مجوزی بدهد آن را قبول می‌کند، پس همه‌ی سلب‌ها برمی‌گشتند |
| `clearance.E008` | `clearance.roles` یا `clearance.translations` بدون `'clearance'`، یا قبل از آن، نصب شده |
| `clearance.E009` | یک ویوی `PolicyRequiredMixin` نمی‌تواند از policyاش بپرسد |
| `clearance.E010` | `ROLE_RESOLVER` یا `ROLE_ATTRIBUTE` قابل استفاده نیست |
| `clearance.E011` | `CLEARANCE` دیکشنری نیست، یا کلیدی دارد که کتابخانه نمی‌شناسد |
| `clearance.E012` | یک فیلد محافظت‌شده فیلدی از مدلش نیست |

`clearance_check` (یک دستور، چون دیتابیس را می‌خواند) مجوزهای بدون scope،
scopeهایی که مدلی دیگر ارائه نمی‌دهد، و مجوزهایی که هیچ‌کس ندارد را فهرست
می‌کند.

---

## ۱۵. Signalها

هر کدام بعد از commit شدن تراکنش فرستاده می‌شود: `bundle_created`،
`bundle_changed`، `bundle_deleted`، `bundle_given`، `bundle_taken`،
`permission_granted`، `permission_revoked`، `permission_restored`،
`scope_changed`، و با `clearance.roles`، `role_assigned`، `role_unassigned` و
`starting_bundles_given`. هر کدام شخص یا بسته، چیزی که تغییر کرده و `actor` را
همراه دارد.

---

## ۱۶. چه چیزی از DayarDarman می‌آید

| DayarDarman | django-clearance |
|---|---|
| `build_permissions`، `RECORD_ACTIONS` | همان، به‌اضافه‌ی فیلدهای محافظت‌شده |
| `PermissionRegistry`، `BasePolicy`، `PolicyPermission` | همان؛ hookها scope ردیف را رعایت می‌کنند |
| `ScopedQuerySet` با یک hook برای هر نقش | یک hook برای هر **scope**، که برای هر مجوز در یک بسته انتخاب می‌شود |
| `RoleAccessGroup` | `RoleBundle`: بسته‌های اولیه‌ی یک نقش |
| `ONLY_FOR` | `ROLE_CEILINGS`، که در Backend اعمال می‌شود |
| `PermissionRevocation`، `RevocableModelBackend` | همان، در هسته |
| `AccessGroupTranslation` | `BundleTranslation` |
| ردیف‌های `AuditService` | signalها |

---

## ۱۷. سازگاری

| | پشتیبانی | تست در CI |
|---|---|---|
| Python | 3.11 تا 3.14 | همه‌شان |
| Django | 5.2 LTS، 6.0، 6.1 | هر کدام با همه‌ی نسخه‌های پایتونی که پشتیبانی می‌کند |
| Django REST framework | 3.16 و بالاتر، اختیاری | آخرین نسخه |
| دیتابیس | هر چیزی که جنگو پشتیبانی می‌کند | PostgreSQL و SQLite |

---

## ۱۸. قراردادهای این ریپو

* **کد فقط به انگلیسی**؛ هر پیام برای ترجمه علامت‌گذاری می‌شود و فارسی در
  `src/clearance/locale/fa/` است. این قاعده را code review نگه می‌دارد.
* **مستندات به انگلیسی و فارسی** که با هم تغییر می‌کنند؛ کد در سند فارسی دقیقاً
  مثل سند انگلیسی می‌ماند.
* **docstring هر ماژول می‌گوید چرا وجود دارد**؛ و هر قاعده، بدون آن چه چیزی
  خراب می‌شد.
* **اسم تست‌ها از رفتاری است که نگه می‌دارند**، و هر ادعایی درباره‌ی هزینه با
  `django_assert_num_queries` شمرده می‌شود.
* **ruff** و **mypy** (strict) روی هر تغییر؛ هر مرحله یک pull request.

---

## ۱۹. مرحله‌ها

مرحله‌های ۰ تا ۳ ساخته شده‌اند. این ویرایش مرحله‌ی ۳ را عوض می‌کند: محدودسازی
ردیف که بر اساس نقش بود، به scope برای هر مجوز تبدیل می‌شود، و نقش‌ها به مرحله‌ی
خودشان می‌روند.

| مرحله | تحویل | |
|---|---|---|
| 0 | طراحی | انجام شده |
| 1 | اسکلت و CI | انجام شده |
| 2 | مجوزها، policyها، registry | انجام شده |
| 3 | تنظیمات، ویوهای جنگو، decorator، checkها - ساخته‌شده حول نقش‌ها | انجام شده؛ در 3b بازسازی می‌شود |
| **3b** | لایه‌های ۱ و ۲: `ScopeGrant`، `PermissionRevocation`، `ClearanceBackend`، `grants`، `AccessService`، scopeهای اسم‌دار و `visible_to(user, action)`، hookهایی که scope را رعایت می‌کنند؛ کد نقش‌های مرحله‌ی ۳ به مرحله‌ی ۷ منتقل می‌شود | |
| 4 | لایه‌ی ۳: فیلدهای محافظت‌شده - مجوزها، `fields`، mixinهای فرم، ویو و ادمین | |
| 5 | DRF: پل، ویوست‌ها، mixin مربوط به serializer، و checkهایشان | |
| 6 | پنل ادمین: صفحه‌های مجوز، بسته و کاربر | |
| 7 | لایه‌ی ۴: `clearance.roles` - resolverها، سقف‌ها، بسته‌های اولیه، `clearance_seed` | |
| 8 | `clearance.translations` | |
| 9 | مستندات، یک پروژه‌ی نمونه، کاتالوگ فارسی | |
| 10 | استفاده در iranbobco؛ تگ `0.1.0`، public کردن، انتشار | |

## ۲۰. بعد از 0.1

* **مجوز روی یک ردیف** - «علی می‌تواند سفارش ۴۲ را ویرایش کند» - کنار scopeها.
* **فیلدهای محافظت‌شده با scope ردیف** - قیمت سفارش‌های شعبه‌ی خودش.
* **قواعد ایمنی تغییر دسترسی**: هیچ‌کس دسترسی خودش را تغییر نمی‌دهد؛ هیچ‌کس چیزی
  را که خودش ندارد به کسی نمی‌دهد؛ تغییری که بعد از آن هیچ‌کس نتواند دسترسی‌ها
  را مدیریت کند رد می‌شود.
* **endpointهای REST** برای صفحه‌ی مجوزها و برای «من چه کارهایی می‌توانم بکنم».

---

## ۲۱. تصمیم‌ها

تصمیم‌های صاحب پروژه:

1. هر import اسم ماژولش را می‌آورد.
2. صاحب حق کپی amir mohammad kashanchian است.
3. قدیمی‌ترین نسخه‌ی پایتون 3.11 است.
4. resolver پیش‌فرض نقش `user.role` را می‌خواند.
5. ویوهای خود جنگو همان پلی را می‌گیرند که DRF دارد.
6. پنل ادمین مجوزها را نشان می‌دهد و بسته می‌سازد.
7. مجوزها و بسته‌ها در 0.1 به هر زبانی نام‌گذاری می‌شوند.
8. **بسته‌های دسترسی هسته‌اند**؛ پروژه به نقش نیازی ندارد.
9. **scope ردیف برای هر مجوز** داخل بسته انتخاب می‌شود.
10. **نقش‌ها محدود می‌کنند و می‌توانند بسته‌ی اولیه بدهند** - که سقف آن را هم
    محدود می‌کند.
11. **فیلدها می‌توانند محافظت شوند**، هر کدام با مجوز دیدن و ویرایش خودش.

12. مجوزی که **بدون scope** داده شده، به **`default_scope`** مدل می‌رسد - و
    وقتی برنامه‌نویس هیچ‌کدام را نام نبرده، به **هیچ ردیفی**.
13. در 0.1، **مجوزهای یک فیلد مال شخص است**، نه با scope ردیف.
14. **سقف‌ها در کد نوشته می‌شوند**، نه در پنل ادمین، تا هر کاری که مدیر سایت
    بکند پابرجا بمانند.
15. **فیلد محافظت‌شده حذف می‌شود** وقتی خواندنش مجاز نیست، و **مقداری که برایش
    فرستاده شود رد می‌شود** وقتی نوشتنش مجاز نیست.
16. **`'clearance'` یک اپ با مدل است** که لایه‌های ۱ تا ۳ را نگه می‌دارد.
17. **همه‌ی لایه‌ها اختیاری‌اند** و فقط روی مدل‌ها و در پروژه‌هایی استفاده
    می‌شوند که آن‌ها را بخواهند؛ تنها چیز اجباری `ClearanceBackend` است.
