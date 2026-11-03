# django-clearance

Role, policy and row-level access control for Django. Denied by default.

[فارسی](README.fa.md)

> Work in progress. What it will be is in the design:
> [`docs/design.md`](docs/design.md).

## Working on it

Every check runs through [nox](https://nox.thea.codes), the same sessions
locally and in CI. With [uv](https://docs.astral.sh/uv/) installed, a Python
that is missing is fetched for you.

```bash
uv tool install nox
```

```bash
nox -s lint
```

```bash
nox -s types
```

```bash
nox -s tests
```

`tests` runs every supported Python and Django; one combination is
`nox -s "tests(3.13-django6.1)"`, and `nox -l` lists them all.

The suite uses SQLite unless told otherwise. To run it on PostgreSQL, as CI
does, set `CLEARANCE_TEST_DATABASE=postgres`; the connection is read from the
standard `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `PGDATABASE`
variables (defaults: `localhost`, `5432`, `postgres`, `postgres`,
`clearance`).

```bash
CLEARANCE_TEST_DATABASE=postgres nox -s tests
```

## Licence

BSD 3-Clause - see [`LICENSE`](LICENSE).
