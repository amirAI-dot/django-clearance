# Management commands

## `clearance_sync`

Makes the database hold what the [`ACCESS` file](access-file.md) declares.

```bash
python manage.py clearance_sync --dry-run    # what would change, writing nothing
python manage.py clearance_sync --check      # in CI: fail when the database differs
python manage.py clearance_sync              # apply it, and say what changed
```

| option | what it does |
|---|---|
| none | lists every change, then applies them in one transaction |
| `--dry-run` | lists every change and writes nothing |
| `--check` | lists every change and fails when there is any - for CI |

`--dry-run` and `--check` cannot be given together. Each change is a line:
`+` made, `~` changed, `-` deleted, with what it is about.

It fails, changing nothing:

* when `CLEARANCE['ACCESS']` names no file, or the file cannot be read;
* when the file cannot be applied - a permission, a scope or a bundle that
  does not exist;
* when the safety rules refuse it - a sync that would leave nobody able to
  manage access.

With `SYNC_ON_MIGRATE`, it runs once at the end of every forward `migrate`.

## `clearance_check`

Says what the database holds that gives no access, or may not be meant - what
no system check can see, because it is in the rows, not the code.

```bash
python manage.py clearance_check
```

**Errors** fail the command - each is something made to give access that
now gives none, silently:

| finding | what it is |
|---|---|
| `broken_rule` | a rule scope that no longer checks out - its field gone, or protected since. It reaches nothing |
| `broken_status_action` | a status action whose field is gone, or holds those values no more |
| `lost_scope` | a grant whose scope its model offers no more. It reaches no rows |

**Warnings** are listed without failing - each is something somebody may not
mean:

| finding | what it is |
|---|---|
| `scope_needed` | a grant with no scope, on a model whose default reaches no rows |
| `unaccounted_permission` | a permission no model, field, status action or code accounts for - an action gone from the code, or one made by hand. It does nothing |

With `--verbosity 2`, it also says how many permissions nobody holds. With
nothing found, it says *Nothing is wrong.* The overview page of the admin
site shows the same findings.

It can stand in CI beside `check`:

```bash
python manage.py check && python manage.py clearance_check
```
