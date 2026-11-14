# 11. Access as code

The bundles and roles a project always has can live in a file, reviewed like
code and the same on every machine. The shop's:

```python
--8<-- "example/config/access.py"
```

The settings name it, and every `migrate` applies it:

```python
CLEARANCE = {'ACCESS': 'config.access.ACCESS', 'SYNC_ON_MIGRATE': True}
```

Or by hand:

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

## Who owns what

**The file owns what it names, and nothing else.** A bundle or a role the
file names is shown read only in the admin site, with a note saying so -
see the role page in [step 10](10-roles.md). A bundle an administrator makes
is theirs, and the file never touches it.

**Who is given a bundle or a role is not the file's to say.** That stays in
the admin site - or, in the shop, in `example_data`.

A status action of a model that keeps Django's permissions goes in the file
too, under `status_actions`:

```python
ACCESS = {
    'status_actions': {
        'shop.Payment': {'refund': {'field': 'state', 'to': ['refunded'], 'from': ['paid']}},
    },
}
```

Start-up refuses a file naming something that cannot be - a permission not
written `app_label.codename`, a model not installed, a field or a value its
model does not have (E001).
