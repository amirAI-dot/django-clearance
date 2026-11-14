# Contributing

## Getting the code running

```bash
git clone https://github.com/amirAI-dot/django-clearance.git
cd django-clearance
python -m pip install nox
```

Everything is run through nox, so every machine - and CI - runs the same
thing:

| session | what it holds |
|---|---|
| `nox -s lint` | ruff, the code and its formatting |
| `nox -s types` | mypy, strict |
| `nox -s tests` | the suite, on every supported Python and Django, with 100% coverage |
| `nox -s browser` | the admin site's pages in a real browser |
| `nox -s messages` | the Persian catalogues hold every marked string, and nothing more |
| `nox -s package` | the package builds and installs |
| `nox -s docs` | this site builds, with no warning |
| `nox -s screenshots` | the pictures of the admin site, taken again |

One combination of the suite, while working:

```bash
nox -s "tests(3.13-django6.1)"
```

## The conventions

* **English only in the code.** Every message a person reads is marked for
  translation; the Persian lives in the catalogues. A Persian string in a
  test is written as `\u` escapes - a test holds the source to ASCII.
* **A test is named after the behaviour it holds** - what would go wrong in
  the world if it failed, not which module it covers.
* **Asking is cheap, and counted.** A change that adds a query per row is a
  defect; a test counts the queries and asks again with more rows.
* **Every module's docstring says why it exists.**
* **The documentation is in English and Persian**, changed together. A page
  and its Persian twin have the same headings, the same tables and the same
  code.

## A change to what a person reads

After marking a string:

```bash
nox -s messages
```

The session extracts the strings again and fails on any difference - add the
Persian for what it added, then compile the catalogue with
`django-admin compilemessages` in `src/clearance`.

## A change to a page of the admin site

Take the pictures again, so none falls behind the page it shows:

```bash
nox -s screenshots
```

## A pull request

One change per pull request, with its tests, and its line in the changelog -
`CHANGELOG.md` and `CHANGELOG.fa.md`, under *Unreleased*. CI runs every
session above.
