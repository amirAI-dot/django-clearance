# نقش‌هایی که روی مدل کاربر هستند

پروژه‌ای که مدل کاربرش از قبل ستون `role` دارد، نقش‌ها را از همان می‌خواند، نه از
نقش‌هایی که در پنل ادمین داده می‌شوند.

```python
class Person(AbstractUser):
    role = models.CharField(max_length=40, blank=True)
```

```python
INSTALLED_APPS = [..., 'clearance', 'clearance.roles']

CLEARANCE = {
    'ROLE_RESOLVER': 'clearance.roles.resolvers.AttributeResolver',
    'ROLE_ATTRIBUTE': 'role',
}
```

هر مقدار ستون کد یک نقش است: یک `Role` با کد `manager` به هر کسی که `role`ش
`manager` است بسته‌های آغازین و سقفش را می‌دهد. خود نقش‌ها - سقف‌ها و بسته‌های
آغازینشان - هنوز در پنل ادمین یا فایل `ACCESS` ساخته می‌شوند.

## چه کسی ستون را می‌نویسد

نوشتن `role` یعنی دادن یک نقش. پس در پنل ادمین فقط ابرکاربر آن را می‌نویسد. فرم یا
API خود پروژه که آن را می‌نویسد هم باید همین‌قدر سخت‌گیر باشد: هر کس آن را بنویسد
نقش را داده، و همه‌ی قانون‌های دادن نقش را دور زده.

## در یک policy

```python
from clearance.roles.resolvers import has_role

has_role(user, 'manager')
```

`AttributeResolver` یک ستون را می‌خواند، هیچ‌وقت یک property را نه: در همان یک
کوئری‌ای خوانده می‌شود که هر بررسی می‌سازد. نقشی که جای دیگری نگه داشته می‌شود -
جدولی از خود پروژه، یک دایرکتوری بیرونی - resolver خود پروژه است، که از
`RoleResolver` ارث می‌برد.
