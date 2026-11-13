# راهنما

[English](guide.md)

چطور django-clearance را در یک پروژه به کار ببرید، از نصب تا آخرین اپ اختیاری.
اینکه چرا این‌طور ساخته شده در [سند طراحی](design.fa.md) آمده؛ پروژه‌ای که همه‌ی
بخش‌هایش را به کار می‌برد در [`example/`](../example/README.fa.md) است.

---

## ۱. چه کاری می‌کند

چهار لایه، که هر کدام به یک پرسش جواب می‌دهد و هر کدام بدون لایه‌ی بعدی هم کار
می‌کند:

| لایه | پرسش | کجا تصمیم گرفته می‌شود |
|---|---|---|
| بسته‌ها | این شخص چه مجوزهایی دارد؟ | پنل ادمین، یا فایل `ACCESS` |
| دامنه‌های ردیف | یک مجوز به کدام ردیف‌ها می‌رسد؟ | دامنه‌ای که کنار هر مجوز انتخاب می‌شود |
| فیلدهای محافظت‌شده | کدام فیلدها را می‌تواند بخواند، و بنویسد؟ | دو مجوزِ خود آن فیلد |
| نقش‌ها، اختیاری | این شخص، هر چه به او بدهند، چه چیزی را هیچ‌وقت نمی‌تواند داشته باشد؟ | سقف یک نقش |

**پیش‌فرض، رد کردن است.** هیچ کس چیزی را که به او داده نشده ندارد، یک مجوز تا
وقتی دامنه‌ای نگوید به کدام ردیف‌ها می‌رسد به هیچ ردیفی نمی‌رسد، و viewای که
نتواند بگوید از کدام policy بپرسد، موقع بالا آمدن پروژه رد می‌شود.

---

## ۲. نصب

```bash
pip install 'django-clearance[drf]'    # or django-clearance, without DRF
```

```python
INSTALLED_APPS = [
    'clearance.admin.apps.ClearanceAdminConfig',   # instead of 'django.contrib.admin'
    ...
    'clearance',
    'clearance.roles',          # optional: roles and ceilings
    'clearance.translations',   # optional: names in every language
]

# In place of django.contrib.auth.backends.ModelBackend (E006, E007).
AUTHENTICATION_BACKENDS = ['clearance.backends.ClearanceBackend']

# With DRF: every view asks the model's policy, unless it names another.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['clearance.drf.permissions.ModelPolicyPermission'],
}
```

```bash
python manage.py migrate
```

اپ‌های اختیاری بعد از `'clearance'` می‌آیند (E008). اپ ادمین هم اختیاری است؛ بدون
آن هیچ صفحه‌ی دسترسی‌ای وجود ندارد و هیچ چیز دیگری عوض نمی‌شود.

---

## ۳. مجوزها

یک مدل می‌تواند مجوزهای خود Django را نگه دارد - `shop.view_order`، `add_order`،
`change_order`، `delete_order` - و لازم نیست هیچ چیزی عوض شود. یا مجوزهای کتابخانه
را تعریف کند، که به اسم کاری که انجام می‌شود نام‌گذاری شده‌اند، نه به اسم viewهای
Django:

```python
from clearance.permissions import DEFAULT_ACTIONS, build_permissions

class Order(models.Model):
    ...
    class Meta:
        default_permissions = ()        # E014 without it
        permissions = build_permissions(
            'order',
            _('orders'),
            actions=(*DEFAULT_ACTIONS, 'approve'),
            labels={'approve': _('Can approve or reject %(resource)s')},
        )
```

این یعنی `shop.order_view`، `order_create`، `order_edit`، `order_delete` و
`order_approve`. `permission_for(Order, 'edit')` به هر دو سبک جواب می‌دهد، پس هیچ
جای دیگر پروژه لازم نیست بداند یک مدل کدام را نگه می‌دارد.

---

## ۴. بسته‌ها

بسته همان `Group` خود Django است: مجوزهایی که با هم داده می‌شوند، هر کدام با یک
دامنه. در پنل ادمین ساخته می‌شوند - *Access*، *Bundles*، جدولی که هر ردیفش یک
مدل و هر ستونش یک اکشن است - یا در کد:

```python
from clearance.services import AccessService

access = AccessService(actor=request.user)

managers = access.create_bundle(
    'Branch managers',
    grants={'shop.order_view': 'branch', 'shop.order_edit': 'branch'},
)
access.give_bundle(person, managers)
access.revoke(person, 'shop.order_edit', reason='Under review')
```

`revoke` یک مجوز را از یک شخص می‌گیرد، هر چه بسته‌هایش بدهند، و دلیلش را می‌گوید.
هر تغییری از `AccessService` می‌گذرد، زیر قانون‌های ایمنی (بخش ۱۲)، و وقتی commit
شد یک سیگنال می‌فرستد.

---

## ۵. دامنه‌های ردیف

دامنه می‌گوید یک مجوز به کدام ردیف‌ها می‌رسد. هر مدل در کد دامنه‌هایی پیشنهاد
می‌کند، و مدیر از روی قانون‌ها دامنه‌های بیشتری می‌سازد.

### ۵.۱ در کد

```python
from clearance.querysets import ScopedQuerySet

class OrderQuerySet(ScopedQuerySet):
    scopes = {
        'own': _('Their own orders'),
        'branch': _("Their branch's orders"),
    }

    def scope_own(self, user):
        return Q(customer=user)

    def scope_branch(self, user):
        return Q(branch=user.branch_id)

class Order(models.Model):
    ...
    objects = OrderQuerySet.as_manager()
```

`all` همیشه پیشنهاد می‌شود. `default_scope` چیزی است که یک اعطای بدون دامنه به آن
می‌رسد - به صورت پیش‌فرض هیچ. `OwnedQuerySet` حالت رایج است که یک بار نوشته شده:
`owner_path = 'customer'` دامنه‌ی `own` را می‌دهد.

### ۵.۲ به شکل قانون، در پنل ادمین

*Access*، *Row scopes*، *Build*: یک اسم، *all of* یا *any of*، و شرط‌ها - یک
فیلد، یک عملگر و یک مقدار، که یا ثابت است یا چیزی از خود شخص:

```text
branch      is          the person's branch
status      is one of   pending, approved
```

یک قانون همیشه فقط یک `Q` در Django است، که موقع ذخیره بررسی می‌شود. هیچ‌وقت فیلد
محافظت‌شده یا رمز عبور را نمی‌خواند، و حداکثر از `RULE_DEPTH` رابطه رد می‌شود.
شرطی که به مدل دیگری می‌رسد - مثلاً `customer__email` - آن مدل را می‌خواند، پس
نویسنده‌ی قانون باید اجازه‌ی دیدن همه‌ی ردیف‌های آن مدل را داشته باشد.

### ۵.۳ خواستن ردیف‌ها

```python
Order.objects.visible_to(user, 'edit')     # the orders they may edit
visible(Order.objects.all(), user, 'view')   # the same, for any queryset
```

اعطاها و قانون‌های هر شخص در هر درخواست یک بار خوانده می‌شوند، با تعداد ثابتی
کوئری، هر چند فهرست که صفحه نشان بدهد. این‌ها روی شیء کاربر نگه داشته می‌شوند، همان‌طور
که Django مجوزهای یک شخص را نگه می‌دارد: در پردازه‌ای که بیشتر از یک درخواست زنده
می‌ماند - یک worker، یک websocket - وقتی ممکن است دسترسی کسی عوض شده باشد، کاربر را
دوباره بخوانید، یا آنچه نگه داشته شده را فراموش کنید.

```python
from clearance.grants import forget_grants

forget_grants(user)    # read again, at the next question
```

یک queryset می‌تواند با بازنویسی `visible_to` به شیوه‌ی خودش جواب بدهد؛ آن وقت همه‌ی
درها - یک view، پنل ادمین، یک policy - از آن می‌پرسند. درون این بازنویسی، هم
`visible(self, ...)` و هم `super().visible_to(...)` از روی اعطاها جواب می‌دهند، پس هر
دو آنچه را اعطاها به آن می‌رسند محدودتر می‌کنند:

```python
class OrderQuerySet(ScopedQuerySet):
    def visible_to(self, user, action='view'):
        return visible(self, user, action).filter(archived=False)
```

### ۵.۴ نوشتن ردیف‌ها

دامنه برای چیزی که نوشته می‌شود هم برقرار است. ویوها، serializerها و صفحه‌های
ادمین کتابخانه ردیفی را که بیرون از دامنه‌ی `create` ساخته شود، یا با ویرایش از
ردیف‌هایی که شخص به آن‌ها می‌رسد بیرون برود، رد می‌کنند - با 403، و نوشتن برگردانده
می‌شود. به `create` هم مثل `view` دامنه بدهید: بدون دامنه به `default_scope` مدل
می‌رسد، که روی `ScopedQuerySet`ای که آن را نام نبرده یعنی هیچ ردیفی.
ردیف‌هایی که با هم فرستاده می‌شوند - یک فهرست، `many=True` - تک‌تک بررسی می‌شوند، و
یا همه ذخیره می‌شوند یا هیچ‌کدام. حذف هم چیزی را که شخص اجازه‌ی حذفش را ندارد با خود
نمی‌برد: اگر حذف آبشاری ردیفی بیرون از دامنه‌ی حذف او را، از مدلی که کتابخانه از آن
محافظت می‌کند، با خود ببرد، حذف رد می‌شود (`require_deletable` همین را دستی می‌پرسد).

ویوی خودتان که دستی ذخیره می‌کند همین را می‌پرسد، بعد از ذخیره و داخل همان
تراکنش:

```python
from clearance.writes import require_within_scope

with transaction.atomic():
    order = form.save()
    require_within_scope(request.user, 'create', order)
```

---

## ۶. فیلدهای محافظت‌شده

فیلدی که با یک مجوز خوانده و با مجوزی دیگر نوشته می‌شود:

```python
permissions = build_permissions('order', _('orders'), protected_fields=('price',))
```

این `shop.order_view_price` و `shop.order_edit_price` را اضافه می‌کند. یک فیلد
را می‌شود در پنل ادمین هم محافظت کرد، *Access*، *Protected fields*، بدون هیچ
کدی. در هر دو حالت، فیلدی که شخص اجازه‌ی خواندنش را ندارد از همه‌ی درها کنار
گذاشته می‌شود: serializerهای DRF، فرم‌ها و قالب‌های Django، فرم‌ها، فهرست‌ها،
جستجو، فیلترها و مرتب‌سازی پنل ادمین - و قانون‌ها.

```python
readable_fields(user, Order)   # {'id', 'customer', 'branch', 'item', 'status'}
writable_fields(user, Order)
```

در یک view از Django، `ProtectedFieldsViewMixin` فرم را برای همان شخص می‌سازد و
`readable_fields` را به قالب می‌دهد:

```django
{% if 'price' in readable_fields %}<td>{{ order.price }}</td>{% endif %}
```

درهای کتابخانه فیلد را از هر راه دیگری هم پنهان می‌کنند: serializerی که داخل یک
serializer محافظت‌شده است، فیلدی که با `source=` نام دیگری گرفته، `SearchFilter` و
`OrderingFilter` خود DRF و `DjangoFilterBackend` از django-filter روی
`ScopedModelViewSet`، فیلتری که در نوار نشانی پنل ادمین تایپ شود، و proxy مدل. فیلتر
دیگری که خودتان نوشته‌اید پیش از فیلتر کردن می‌پرسد:

```python
from clearance.fields import path_readable

if path_readable(request.user, Order, 'price__gte'): ...
```

---

## ۷. اکشن‌ها

### ۷.۱ اکشن‌های وضعیت

اکشنی که مقدار می‌نویسد: فقط کسی که اجازه‌ی تأیید دارد *approved* یا *rejected* را
می‌گذارد، و فقط از *pending*.

```python
permissions = build_permissions(
    'order',
    _('orders'),
    actions=(*DEFAULT_ACTIONS, 'approve'),
    status_actions={
        'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
    },
)
```

یا در پنل ادمین، *Access*، *Actions*، بدون هیچ کدی. مقداری که هیچ اکشنی صاحبش
نیست را هر کسی که بتواند ردیف را ویرایش کند می‌نویسد. فرم‌ها و serializerها فقط
مقدارهایی را پیشنهاد می‌کنند که شخص اجازه‌ی نوشتنشان را دارد:

```python
writable_values(user, Order, 'status', order)   # {'pending', 'delivered'}
```

### ۷.۲ اکشن‌هایی که در کد پیدا می‌شوند

یک `@action` روی یک viewset، یک اکشن ادمین، `policy_action` یک view: هر کدام یک
اکشن است، و `migrate` مجوزش را می‌سازد.

```python
class OrderViewSet(ScopedModelViewSet):
    @action(detail=True, methods=['post'])
    def print_invoice(self, request, pk=None):    # shop.order_print_invoice
        ...
```

*Access*، *Actions* آن‌ها را فهرست می‌کند، و مجوزهایی را که دیگر چیزی بررسی‌شان
نمی‌کند.

---

## ۸. Policyها

مدلی که policy ندارد از طریق `ModelPolicy` پرسیده می‌شود: مجوزش، در دامنه‌اش.
policy فقط برای قانونی نوشته می‌شود که هیچ مجوزی نمی‌تواند بگوید:

```python
from clearance.policies import BasePolicy
from clearance.registry import registry

class OrderPolicy(BasePolicy):
    model = Order

    def can_edit(self, user, obj=None):
        if not self.has_within_scope(user, 'edit', obj):
            return False
        return obj is None or obj.status != 'delivered'

order_access = registry.register(OrderPolicy)
```

آن را جایی ثبت کنید که موقع بالا آمدن پروژه import شود - `ready()` همان اپ. هر
hook به شکل `can_<action>` است؛ `custom_actions` یک اکشن را به hookی با اسم دیگر
وصل می‌کند. پرسیدن بیرون از یک view:

```python
order_access.policy.allows(user, 'edit', order)
order_access.policy.authorize(user, 'edit', order)    # PermissionDenied if not
```

---

## ۹. Viewها

### ۹.۱ Viewهای Django

```python
from clearance.views import PolicyRequiredMixin, ProtectedFieldsViewMixin, ScopedQuerySetMixin

class OrderEdit(ProtectedFieldsViewMixin, PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):
    queryset = Order.objects.all()
    fields = ('item', 'status', 'price')
```

اکشن از خود view خوانده می‌شود - `ListView` یعنی `list`، `UpdateView` یعنی
`edit` - یا با `policy_action` نام برده می‌شود. یک view تابعی:

```python
@policy_required(order_access.policy, 'refund')
def refund(request, pk):
    ...
```

### ۹.۲ DRF

```python
from clearance.drf.viewsets import ScopedModelViewSet

class OrderViewSet(ScopedModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer       # written knowing nothing of the library
```

`ScopedModelViewSet` ردیف‌ها را محدود می‌کند، برای هر اکشن از policy مدل
می‌پرسد، و فیلدهایی را که شخص اجازه‌ی خواندنشان را ندارد کنار می‌گذارد. نوشتنی
که فیلدی را نام ببرد که شخص اجازه‌ی نوشتنش را ندارد - یا مقدار وضعیتی که اجازه‌ی
گذاشتنش را ندارد - یک 400 است که آن فیلد را نام می‌برد. هر بخش به تنهایی روی هر
view از DRF کار می‌کند: `ScopedQuerySetMixin`، `ModelPolicyPermission`،
`ProtectedSerializerMixin`. viewای که مدل ندارد policyاش را نام می‌برد:

```python
class OrderReport(APIView):
    permission_classes = (PolicyPermission,)
    policy = order_access.policy
    policy_action = 'report'
```

**ردیف مرتبط ردیفی است که شخص اجازه‌ی دیدنش را دارد.** فیلدی از serializer که ردیف
مرتبط را انتخاب می‌کند ردیف‌هایی از آن مدل را می‌پذیرد که شخص اجازه‌ی دیدنشان را
دارد - هر کلید دیگری رد می‌شود، انگار وجود ندارد. داده‌ی مرجعی که همه از آن انتخاب
می‌کنند با `SignedInReadQuerySet` خوانده می‌شود:

```python
class Branch(models.Model):
    objects = SignedInReadQuerySet.as_manager()   # anybody signed in may choose one
```

**viewای که هیچ رکوردی نگه نمی‌دارد این را می‌گوید.** وقتی `ModelPolicyPermission`
پیش‌فرض است، viewای که نه مدل دارد و نه policy موقع بالا آمدن پروژه رد می‌شود
(E009) - از جمله view ریشه‌ی `DefaultRouter` خود DRF. مجوزی را که لازم دارد به آن
بدهید:

```python
class ShopRouter(routers.DefaultRouter):
    class APIRootView(routers.APIRootView):
        permission_classes = (IsAuthenticated,)
```

---

## ۱۰. پنل ادمین

`ClearanceAdminConfig` پنل ادمین Django را با پنل کتابخانه عوض می‌کند، و
کلاس‌های `ModelAdmin` پروژه همان‌طور می‌مانند که Django مستند کرده. هر صفحه از
policy مدل می‌پرسد، فقط ردیف‌هایی را نشان می‌دهد که شخص به آن‌ها می‌رسد، فیلدهای
محافظت‌شده را کنار می‌گذارد یا قفل می‌کند، فقط مقدارهای وضعیتی را پیشنهاد می‌کند
که شخص اجازه‌ی نوشتنشان را دارد، و هر اکشن ادمین را فقط به کسی پیشنهاد می‌کند که
مجوزش را دارد.

زیر *Access*:

| صفحه | چه کاری آن‌جا انجام می‌شود |
|---|---|
| Overview | بسته‌ها، نقش‌ها، افراد دارای دسترسی، و آنچه `clearance_check` پیدا کرده |
| Bundles | یک بسته به شکل جدول، و اینکه چه کسی آن را دارد |
| People | همه‌ی وضعیت یک شخص، و اینکه هر مجوز از کجا آمده |
| Permissions | همه‌ی مجوزها، و اینکه چه کسی هر کدام را دارد |
| Row scopes | سازنده‌ی قانون |
| Protected fields | علامت زدن فیلدها، مدل به مدل |
| Actions | اکشن‌های وضعیت؛ اکشن‌هایی که در کد پیدا شده‌اند |
| Roles | با `clearance.roles` |

این صفحه‌ها مجوزهای خود کتابخانه را لازم دارند: `clearance.permission_view` برای
دیدن، و `permission_create`، `permission_edit` و `permission_delete` برای تغییر
دادن. به فارسی، راست به چپ خوانده می‌شوند.

---

## ۱۱. دسترسی به صورت کد

بسته‌ها، اکشن‌های وضعیت و نقش‌هایی که یک پروژه همیشه دارد می‌توانند در یک فایل
باشند، و مثل کد بازبینی شوند:

```python
# config/access.py
ACCESS = {
    'bundles': {
        'Branch managers': {'shop.order_view': 'branch', 'shop.order_approve': 'branch'},
        'Customers': {'shop.order_view': 'own', 'shop.order_create': 'own'},
    },
    'status_actions': {                  # for a model keeping Django's permissions
        'shop.Payment': {'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']}},
    },
    'roles': {                           # with clearance.roles
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.order_view', 'shop.order_create'],
            'bundles': ['Customers'],
        },
    },
}
```

```python
CLEARANCE = {'ACCESS': 'config.access.ACCESS', 'SYNC_ON_MIGRATE': True}
```

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

فایل صاحب چیزی است که نام می‌برد، و نه هیچ چیز دیگر؛ پنل ادمین آن را فقط‌خواندنی
نشان می‌دهد. اینکه یک بسته یا نقش به چه کسی داده شود در پنل ادمین می‌ماند.

---

## ۱۲. قانون‌های ایمنی

هر تغییری - در پنل ادمین، در کد، از فایل `ACCESS` - وقتی بگذارد کسی به خودش
بیشتر بدهد رد می‌شود:

* هیچ کس دسترسی خودش را، یا بسته یا نقشی را که خودش دارد، تغییر نمی‌دهد؛
* هیچ کس مجوز یا دامنه‌ای را که خودش ندارد به کسی نمی‌دهد - و مجوزی را که گرفته
  شده پس نمی‌دهد، ردیف‌های دامنه‌ی قانونی‌ای را که دیگران مجوز را در آن دارند بازتر
  نمی‌کند، و نمی‌گذارد یک اکشن وضعیت از مقدارهای بیشتری بنویسد؛
* نقش دومی که سقف کسی را بازتر کند `role_ceiling_edit` می‌خواهد؛
* یک حساب را فقط کسی تغییر می‌دهد یا حذف می‌کند که دست‌کم همه‌ی آنچه آن حساب دارد را
  داشته باشد - گذاشتن رمز یک حساب یعنی وارد شدن با آن؛
* تغییری که بعد از آن هیچ کس نتواند دسترسی را مدیریت کند رد می‌شود؛
* چیزی که فایل `ACCESS` صاحبش است فقط در همان فایل تغییر می‌کند.

ردشدن یک `AccessRefused` است که قانون را نام می‌برد. ابرکاربر همه‌ی مجوزها را
دارد و به همه‌ی ردیف‌ها می‌رسد.

---

## ۱۳. نقش‌ها

با `clearance.roles`، نقش یعنی اینکه یک شخص چه کسی است: یک مشتری، یک مدیر شعبه.
دو چیز می‌دهد:

* **بسته‌های آغازین** - هر کسی این نقش را دارد آن‌ها را دارد، بی‌آنکه یکی‌یکی به او
  داده شوند؛
* **یک سقف** - بیشترین چیزی که هیچ‌وقت می‌تواند داشته باشد، هر چه بسته‌ها یا اعطاها
  به او بدهند. نقشی که سقف ندارد هیچ چیز را محدود نمی‌کند.

نقش‌ها در پنل ادمین یا با `RoleService(actor).assign(person, role)` داده می‌شوند،
و resolverای که `ROLE_RESOLVER` نام می‌برد آن‌ها را می‌خواند. `AttributeResolver`
به جایش آن‌ها را از خود کاربر می‌خواند - از فیلدی که `ROLE_ATTRIBUTE` نام می‌برد،
و در سایت ادمین فقط superuser آن را می‌نویسد: نوشتنش یعنی دادن نقش. در کد:

```python
from clearance.roles.resolvers import has_role

has_role(user, 'manager')
```

---

## ۱۴. اسم‌ها در همه‌ی زبان‌ها

صفحه‌ها، پیام‌ها و اسم مجوزهای خود کتابخانه به انگلیسی و فارسی (`fa`) هستند؛
کاتالوگ خود پروژه برچسب‌هایی را که به `build_permissions` می‌دهد ترجمه می‌کند. با
`clearance.translations`، مدیر می‌تواند یک مجوز، بسته یا نقش را هم در همه‌ی
زبان‌های `LANGUAGES` نام‌گذاری کند، از صفحه‌ی خود آن:

```python
from clearance.labels import label_of, labels_in

label_of(bundle)                      # in the active language
labels = labels_in('fa')              # every name of a language, in one query
labels.of(permission)
```

```django
{% load clearance %}{{ bundle|label:labels }}
```

یک اسم از زبان خواننده خوانده می‌شود، بعد زبان پایه‌اش، بعد چیزی که کد می‌گوید،
بعد ردیف.

---

## ۱۵. بررسی

موقع بالا آمدن پروژه، system checkهای Django چیزی را که نمی‌تواند کار کند رد
می‌کنند: backendای که نیست یا دوتاست، viewای که نمی‌تواند از policy بپرسد،
serializerای که فیلد محافظت‌شده را نشان می‌دهد، پنل ادمینی که مال کتابخانه نیست.
فهرست کامل در سند طراحی، بخش ۱۷، آمده.

چیزی را که فقط پایگاه داده می‌تواند بگوید `clearance_check` می‌گوید:

```bash
python manage.py clearance_check
```

**خطاها** آن را fail می‌کنند - دامنه‌ی قانونی که دیگر درست نیست، اکشن وضعیتی که
فیلد یا مقدارهایش رفته‌اند، اعطایی که مدلش دیگر دامنه‌اش را پیشنهاد نمی‌کند - چون
هر کدام بی‌صدا هیچ دسترسی‌ای نمی‌دهد. **هشدارها** فقط فهرست می‌شوند: اعطای بدون
دامنه روی مدلی که پیش‌فرضش به هیچ ردیفی نمی‌رسد، و مجوزهایی که هیچ چیز
توضیحشان نمی‌دهد.

---

## ۱۶. تنظیمات

همه زیر `CLEARANCE`؛ هیچ کدام لازم نیست.

| کلید | پیش‌فرض | معنی |
|---|---|---|
| `ROLE_RESOLVER` | `'clearance.roles.resolvers.AssignmentResolver'` | نقش‌های هر شخص از کجا خوانده می‌شوند |
| `ROLE_ATTRIBUTE` | `'role'` | چیزی که `AttributeResolver` می‌خواند |
| `ACCESS` | `None` | دسترسی‌ای که در کد تعریف شده، و `clearance_sync` اعمالش می‌کند |
| `SYNC_ON_MIGRATE` | `False` | اجرای `clearance_sync` در پایان هر `migrate` رو به جلو |
| `RULE_DEPTH` | `3` | فیلد یک قانون از چند رابطه می‌تواند رد شود |

کلیدی که کتابخانه نمی‌شناسد رد می‌شود (E011).

---

## ۱۷. سیگنال‌ها

هر کدام وقتی تغییر commit شد فرستاده می‌شود، با `actor` و چیزی که تغییر کرده:
`bundle_created`، `bundle_changed`، `bundle_deleted`، `bundle_given`،
`bundle_taken`، `permission_granted`، `permission_revoked`،
`permission_restored`، `scope_changed`، `scope_rule_saved`،
`scope_rule_deleted`، `field_protected`، `field_unprotected`،
`status_action_saved`، `status_action_deleted`، `actions_found`؛ با
`clearance.roles`، `role_saved`، `role_deleted`، `role_assigned`،
`role_unassigned` و `ceiling_changed`؛ با `clearance.translations`،
`name_changed`.

```python
from clearance import signals

@receiver(signals.permission_revoked)
def tell_security(sender, person, permission, reason, actor, **kwargs):
    ...
```
