# نگه داشتن سابقه‌ی تغییرها

هر تغییری در دسترسی یک سیگنال است که بعد از commit شدن تغییر فرستاده می‌شود - پس
گیرنده هیچ‌وقت تغییری را که برگشت خورده ثبت نمی‌کند. هر کدام `actor` را دارد، کسی
که تغییر را داده، و `None` برای خود سیستم.

```python
# audit/receivers.py
from django.dispatch import receiver

from clearance import signals
from audit.models import AccessChange


@receiver(signals.bundle_given)
def bundle_given(sender, actor, person, bundle, **kwargs):
    AccessChange.objects.create(actor=actor, person=person, what=f'given {bundle}')


@receiver(signals.permission_revoked)
def permission_revoked(sender, actor, person, permission, reason, **kwargs):
    AccessChange.objects.create(
        actor=actor, person=person, what=f'took {permission}: {reason}'
    )
```

گیرنده‌ها را وقتی اپ بالا می‌آید وصل کنید:

```python
class AuditConfig(AppConfig):
    name = 'audit'

    def ready(self):
        from audit import receivers  # noqa: F401
```

همه‌ی سیگنال‌ها و آنچه هر کدام همراه دارد در [مرجع](../reference/signals.md) است.
تغییری که در پنل ادمین، در کد یا با `clearance_sync` انجام شود همان سیگنال است: همه
از همان سرویس‌ها می‌گذرند.

## آنچه سیگنال نیست

اینکه چه کسی یک رکورد را *می‌خواند* تغییری در دسترسی نیست: آن را جایی ثبت کنید که
رکورد خوانده می‌شود - یک view، یک serializer. رد شدن هم تغییر نیست؛ یک
`AccessRefused` است که فراخواننده می‌گیرد، یا یک 403.
