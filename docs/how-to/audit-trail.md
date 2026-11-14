# Keep an audit trail

Every change to access is a signal, sent once the change commits - so a
receiver never records a change that was rolled back. Each carries `actor`,
who made it, `None` for the system.

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

Connect the receivers when the app starts:

```python
class AuditConfig(AppConfig):
    name = 'audit'

    def ready(self):
        from audit import receivers  # noqa: F401
```

Every signal and what it carries is in the [reference](../reference/signals.md).
A change made in the admin site, in code or by `clearance_sync` is the same
signal: they all go through the same services.

## What is not a signal

Who *reads* a record is not a change to access: record it where the record
is read - a view, a serializer. A refusal is not a change either; it is an
`AccessRefused` the caller catches, or a 403.
