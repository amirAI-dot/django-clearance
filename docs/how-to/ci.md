# Check access in CI

Three commands, each failing a build for its own reason:

```bash
python manage.py check                      # what cannot work, by the code
python manage.py clearance_sync --check     # the database differs from the ACCESS file
python manage.py clearance_check            # the database gives no access it was made to give
```

`check` refuses at start-up what cannot work. `clearance_sync --check` fails
when the database differs from the `ACCESS` file, and lists every
difference. `clearance_check` fails on a rule scope, status action or grant
that now reaches nothing, and lists warnings without failing.

## On GitHub Actions

```yaml
- run: python manage.py migrate
- run: python manage.py check
- run: python manage.py clearance_sync --check
- run: python manage.py clearance_check
```

`--check` and `clearance_check` read the database, so they run against one -
a fresh one, migrated, says whether the file applies; a copy of production,
whether production matches it.

## Before a deploy

```bash
python manage.py clearance_sync --dry-run
```

lists what the deploy's sync will change, writing nothing - the review a
change to access deserves before it reaches people.
