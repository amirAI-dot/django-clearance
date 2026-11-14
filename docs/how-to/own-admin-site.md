# Use an admin site of your own

A project with an admin site of its own - a header, a page added - subclasses
the library's. An admin site that is not the library's is refused at
start-up (E016): its pages would not ask the policies, and would show every
protected field.

## The site

```python
# config/admin.py
from clearance.admin.sites import ClearanceAdminSite


class ShopAdminSite(ClearanceAdminSite):
    site_header = 'The shop'
```

## The app that makes it the default

```python
# config/apps.py
from clearance.admin.apps import ClearanceAdminConfig


class ShopAdminConfig(ClearanceAdminConfig):
    default_site = 'config.admin.ShopAdminSite'
```

```python
INSTALLED_APPS = [
    'config.apps.ShopAdminConfig',   # instead of 'clearance.admin.apps.ClearanceAdminConfig'
    ...
]
```

`admin.site`, and every `@admin.register`, is then the project's site, with
every rule and the access pages.

## Pages of your own

A project's own `ModelAdmin` classes need nothing: the site gives each the
rules. A page beside the access pages is a `PageSet`, mounted once:

```python
ShopAdminSite.add_pages(ReportPages)
```
