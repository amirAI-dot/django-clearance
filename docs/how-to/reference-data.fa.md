# داده‌ی مرجع که همه می‌خوانند

فهرست شعبه‌ها، انواع وام: همه‌ی کسانی که وارد شده‌اند آن‌ها را می‌خوانند تا یکی را
انتخاب کنند، و کم‌تر کسی تغییرشان می‌دهد. بستن خواندن آن‌ها از چیزی محافظت
نمی‌کند و باعث می‌شود هر فرمی انتخاب را رد کند.

## ردیف‌ها

```python
from clearance.querysets import SignedInReadQuerySet


class Branch(models.Model):
    name = models.CharField(max_length=80)

    objects = SignedInReadQuerySet.as_manager()
```

همه‌ی ردیف‌ها، برای هر کسی که وارد شده، هر چه داشته باشد - پس فیلدی در serializer یا
فرم که شعبه انتخاب می‌کند همه‌ی شعبه‌ها را پیشنهاد می‌کند. کسی که وارد نشده، یا
حسابش غیرفعال است، به هیچ کدام نمی‌رسد.

## نوشتن‌ها

اینکه چه کسی می‌تواند شعبه‌ای را تغییر دهد هنوز یک مجوز است: `change_branch`، که
مثل هر مجوز دیگری داده می‌شود. برای APIای که شعبه‌ها را برای هر کسی که وارد شده
فهرست می‌کند، به مدل policyای بدهید که همین‌طور می‌خواند:

```python
from clearance.policies import SignedInReadPolicy
from clearance.registry import registry


class BranchPolicy(SignedInReadPolicy):
    model = Branch


registry.register(BranchPolicy)
```

خواندن برای هر کسی که وارد شده باز است؛ ساختن، ویرایش و حذف از مجوزها می‌پرسند.
