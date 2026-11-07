"""
Every check the project runs, defined once - locally and in CI alike.

    nox -l                                   list the sessions
    nox -s lint                              lint and formatting
    nox -s types                             mypy
    nox -s tests                             every supported Python and Django
    nox -s "tests(3.13-django6.1)"           one combination

CI runs these same sessions, built from the same table, so a check that
passes here passes there and a supported version cannot be left out of one.
Pythons that are not installed are fetched by uv.
"""

import nox

nox.needs_version = '>=2025.2.9'
nox.options.default_venv_backend = 'uv|virtualenv'
nox.options.sessions = ['lint', 'types', 'tests']

#: Every supported Django release, and the Pythons that release supports.
#: Adding a release, or dropping one, is a change to this table only.
SUPPORTED: dict[str, tuple[str, ...]] = {
    '5.2': ('3.11', '3.12', '3.13', '3.14'),
    '6.0': ('3.12', '3.13', '3.14'),
    '6.1': ('3.12', '3.13', '3.14'),
}

NEWEST_DJANGO = max(SUPPORTED, key=lambda release: tuple(map(int, release.split('.'))))
NEWEST_PYTHON = SUPPORTED[NEWEST_DJANGO][-1]

MATRIX = [(python, django) for django, pythons in SUPPORTED.items() for python in pythons]


def django_release(release: str) -> str:
    """The requirement that installs the newest patch of one Django release."""
    return f'django~={release}.0'


@nox.session(python=NEWEST_PYTHON)
def lint(session: nox.Session) -> None:
    """Lint and formatting."""
    session.install('--group', 'lint')
    session.run('ruff', 'check', '.')
    session.run('ruff', 'format', '--check', '.')


@nox.session(python=NEWEST_PYTHON)
def types(session: nox.Session) -> None:
    """mypy, strict, over the library's source."""
    session.install('-e', '.[drf]', '--group', 'types', django_release(NEWEST_DJANGO))
    session.run('mypy')


@nox.session
@nox.parametrize(
    'python,django',
    MATRIX,
    ids=[f'{python}-django{django}' for python, django in MATRIX],
)
def tests(session: nox.Session, django: str) -> None:
    """The suite, against one Python and one Django release."""
    session.install('-e', '.', '--group', 'test', django_release(django))
    # The library ships migrations: one forgotten is a release that cannot migrate.
    session.run(
        'python',
        '-m',
        'django',
        'makemigrations',
        '--check',
        '--dry-run',
        '--settings=tests.project.settings',
        env={'PYTHONPATH': '.'},
    )
    session.run('pytest', '--cov', '--cov-report=term', *session.posargs)
