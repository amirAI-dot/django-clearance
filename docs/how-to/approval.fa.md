# تأییدی که فقط بعضی می‌توانند بدهند

هر کسی که بتواند وامی را ویرایش کند می‌تواند اصلاحش کند؛ فقط مدیر آن را تأیید
می‌کند، فقط تا وقتی در انتظار است، و هیچ‌وقت وام خودش را نه.

## ۱. اکشن

یک اکشن وضعیت - در مدل:

```python
class Loan(models.Model):
    ...

    class Meta:
        default_permissions = ()
        permissions = build_permissions(
            'loan',
            _('loans'),
            actions=(*DEFAULT_ACTIONS, 'approve'),
            status_actions={
                'approve': {'field': 'status', 'to': ['approved', 'rejected'], 'from': ['pending']},
            },
        )
```

یا بدون کد، در پنل ادمین، *دسترسی*، *اکشن‌ها* - [اکشن‌ها](../admin/actions.md) را
ببینید. در هر دو حالت `loans.loan_approve` ساخته می‌شود، بدون دارنده.

## ۲. چه کسی می‌تواند

`loan_approve` را به بسته‌ی مدیرها بدهید، با دامنه‌ای که در آن تأیید می‌کنند -
شعبه‌شان، منطقه‌شان. به کسی که آن را ندارد در هیچ فرمی *approved* یا *rejected*
پیشنهاد نمی‌شود، و API هر کدام را رد می‌کند و اسم فیلد را می‌برد.

## ۳. هیچ‌وقت مال خودش

این درباره‌ی ردیف است، نه شخص، پس یک hook در policy است:

```python
from clearance.policies import BasePolicy
from clearance.registry import registry


class LoanPolicy(BasePolicy):
    model = Loan

    def can_approve(self, user, obj=None):
        if not self.has_within_scope(user, 'approve', obj):
            return False
        return obj is None or obj.applicant_id != user.pk


loan_access = registry.register(LoanPolicy)
```

از اکشن وضعیت با خود ردیف از policy پرسیده می‌شود، پس این hook هر جا که وضعیت
نوشته شود برقرار است - پنل ادمین، یک فرم، API.

## ۴. پرسیدن

```python
loan_access.policy.allows(user, 'approve', loan)
writable_values(user, Loan, 'status', loan)    # the values they may set on this loan
```
