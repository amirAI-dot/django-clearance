# دامنه‌ی ردیف با فیلدی از خود شخص

هر کس به ردیف‌های منطقه‌ی خودش می‌رسد: کارشناس وام در شمال وام‌های شمال را
می‌بیند. منطقه‌ی شخص فیلدی از کاربر است.

## به شکل قانون، بدون کد

در پنل ادمین، *دسترسی*، *دامنه‌های ردیف*، برای وام‌ها یک قانون بسازید:

```text
region      is          the person's region
```

یا در کد، همان‌طور که پنل ادمین می‌سازد:

```python
from clearance.services import AccessService

AccessService(actor=request.user).create_scope_rule(
    Loan,
    'region',
    'Their region',
    [{'field': 'region', 'operator': 'is', 'value': {'person': 'region'}}],
)
```

`{'person': 'region'}` یعنی `region` خود شخص؛ `{'person': ''}` یعنی خود شخص؛
`{'person': 'branch__city'}` از یک رابطه عبور می‌کند.

## یا در کد

```python
class LoanQuerySet(ScopedQuerySet):
    scopes = {'region': _('Their region')}

    def scope_region(self, user):
        return Q(region=getattr(user, 'region', None))
```

## هیچ کس خودش را جابه‌جا نمی‌کند

کسی که بتواند `region` خودش را بنویسد به وام‌های منطقه‌ی دیگر می‌رسد - یعنی تغییر
دسترسی خودش. پس هیچ کس روی حساب خودش فیلدی را نمی‌نویسد که تعیین می‌کند به کدام
ردیف‌ها می‌رسد؛ کس دیگری که اجازه‌ی تغییر آن حساب را دارد هنوز می‌تواند.

فیلدهای یک دامنه‌ی قانونی برای کتابخانه شناخته‌شده‌اند و خودبه‌خود قفل می‌شوند.
دامنه‌ی کد، کد است، پس فیلدهایی را که می‌خواند نام ببرید:

```python
CLEARANCE = {'PERSON_FIELDS': ['region']}
```

بعد آن فیلد در صفحه‌ی حساب خود شخص در پنل ادمین و در فرم محافظت‌شده قفل است، و
API آن را رد می‌کند - مگر اینکه همان‌طور که هست برگردانده شود.
