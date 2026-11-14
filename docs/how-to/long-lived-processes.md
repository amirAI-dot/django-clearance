# Workers and websockets

A person's grants and rules are read once and kept on the user object, as
Django keeps a person's permissions - so a request asks the database a fixed
number of times, however many lists it shows.

A request ends, and the user object with it. A process that outlives a
request - a Celery worker, a websocket consumer, a long management command -
keeps the user object as long as it likes, and with it what the person held
when it was read.

## Read the person again

Where access may have changed since, ask about a fresh user object:

```python
user = User.objects.get(pk=user_id)
orders = Order.objects.visible_to(user)
```

Or forget what is kept, and the next question reads it again:

```python
from clearance.grants import forget_grants

forget_grants(user)
```

`forget_grants` forgets the library's grants and Django's permission caches
together, so `has_perm` reads again too.

## A task that runs as somebody

Pass the person's key, not the person:

```python
@shared_task
def export_orders(user_id):
    user = User.objects.get(pk=user_id)
    rows = Order.objects.visible_to(user)
    ...
```

A task queued an hour ago then runs with what the person holds now - a
revoked permission is revoked for the task too.
