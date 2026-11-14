# شروع سریع

یک مدل، یک بسته، و ردیف‌هایی که به آن‌ها می‌رسد - در پروژه‌ای که همان‌طور که
صفحه‌ی قبل گفت [نصب](installation.md) شده.

## ۱. مدلی که ردیف‌هایش مال کسی هستند

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

`OwnedQuerySet` یک دامنه دارد، `own`: ردیف‌هایی که `owner_path` آن‌ها خود شخص
است. `all` همیشه کنار آن هست. مدل مجوزهای خود Django را نگه می‌دارد -
`notes.view_note`، `change_note` و بقیه - و چیزی در آن‌ها عوض نمی‌شود.

```bash
python manage.py makemigrations notes
python manage.py migrate
```

## ۲. هنوز هیچ کس به چیزی نمی‌رسد

```python
from django.contrib.auth.models import User
from notes.models import Note

ana = User.objects.create_user('ana', password='ana', is_staff=True)
ben = User.objects.create_user('ben', password='ben')
Note.objects.create(owner=ana, text="Ana's note")
Note.objects.create(owner=ben, text="Ben's note")

Note.objects.visible_to(ana)      # <NoteQuerySet []>
```

Ana هیچ مجوزی ندارد، پس به هیچ ردیفی نمی‌رسد.

## ۳. یک بسته، با یک دامنه کنار هر مجوز

```python
from clearance.services import AccessService

access = AccessService(actor=None)    # None: the system, not a person
writers = access.create_bundle(
    'Writers',
    grants={'notes.view_note': 'own', 'notes.change_note': 'own'},
)
access.give_bundle(ana, writers)
```

در یک view، `actor` همان `request.user` است: کسی که تغییری می‌دهد نمی‌تواند
بیشتر از آنچه خودش دارد بدهد. همین کار بدون کد در پنل ادمین هم انجام می‌شود،
در *دسترسی*، *بسته‌ها*.

## ۴. پرسیدن

```python
ana = User.objects.get(username='ana')   # read her permissions again

Note.objects.visible_to(ana)             # <NoteQuerySet [<Note: Note object (1)>]>
Note.objects.visible_to(ana, 'edit')     # her note: change_note, in "own"
Note.objects.visible_to(ana, 'delete')   # <NoteQuerySet []>: she holds no delete_note

ana.has_perm('notes.view_note')          # True - Django's own question still works
```

مدل را همان‌طور که Django می‌گوید در پنل ادمین ثبت کنید:

```python
# notes/admin.py
from django.contrib import admin

from notes.models import Note

admin.site.register(Note)
```

با Ana وارد شوید: فهرست یادداشت‌ها یادداشت او را نشان می‌دهد و یادداشت Ben را
نه، و دکمه‌ی حذف ندارد - بدون هیچ کدی درباره‌ی دسترسی در `ModelAdmin`.

## قدم بعدی

[آموزش](../tutorial/index.md) یک فروشگاه کامل می‌سازد: دامنه‌هایی در کد و
قانون‌هایی که در پنل ادمین ساخته می‌شوند، قیمتی محافظت‌شده، تأییدی که فقط بعضی
می‌توانند بدهند، یک policy، یک API، نقش‌ها، و دسترسی به صورت کد.
