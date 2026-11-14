# Quickstart

One model, one bundle, and the rows it reaches - in a project
[installed](installation.md) as the last page says.

## 1. A model whose rows belong to somebody

```python
# notes/models.py
from django.conf import settings
from django.db import models

from clearance.querysets import OwnedQuerySet


class NoteQuerySet(OwnedQuerySet):
    owner_path = 'owner'


class Note(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()

    objects = NoteQuerySet.as_manager()
```

`OwnedQuerySet` offers one scope, `own`: the rows whose `owner_path` is the
person. `all` is always offered beside it. The model keeps Django's own
permissions - `notes.view_note`, `change_note` and the rest - and nothing
about them changes.

```bash
python manage.py makemigrations notes
python manage.py migrate
```

## 2. Nobody reaches anything yet

```python
from django.contrib.auth.models import User
from notes.models import Note

ana = User.objects.create_user('ana', password='ana', is_staff=True)
ben = User.objects.create_user('ben', password='ben')
Note.objects.create(owner=ana, text="Ana's note")
Note.objects.create(owner=ben, text="Ben's note")

Note.objects.visible_to(ana)      # <NoteQuerySet []>
```

Ana holds nothing, so she reaches nothing.

## 3. A bundle, with a scope beside each permission

```python
from clearance.services import AccessService

access = AccessService(actor=None)    # None: the system, not a person
writers = access.create_bundle(
    'Writers',
    grants={'notes.view_note': 'own', 'notes.change_note': 'own'},
)
access.give_bundle(ana, writers)
```

In a view, the actor is `request.user`: whoever makes a change may not give
more than they hold themselves. The same is done with no code in the admin
site, *Access*, *Bundles*.

## 4. Ask

```python
ana = User.objects.get(username='ana')   # read her permissions again

Note.objects.visible_to(ana)             # <NoteQuerySet [<Note: Note object (1)>]>
Note.objects.visible_to(ana, 'edit')     # her note: change_note, in "own"
Note.objects.visible_to(ana, 'delete')   # <NoteQuerySet []>: she holds no delete_note

ana.has_perm('notes.view_note')          # True - Django's own question still works
```

Register the model in the admin site, as Django documents:

```python
# notes/admin.py
from django.contrib import admin

from notes.models import Note

admin.site.register(Note)
```

Sign in as Ana: the list of notes shows hers and not Ben's, and has no
delete button - with nothing about access in the `ModelAdmin`.

## Next

The [tutorial](../tutorial/index.md) builds a whole shop: scopes in code and
rules built in the admin site, a protected price, an approval only some may
give, a policy, an API, roles, and access kept as code.
