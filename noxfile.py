"""
Every check the project runs, defined once - locally and in CI alike.

    nox -l                                   list the sessions
    nox -s lint                              lint and formatting
    nox -s types                             mypy
    nox -s tests                             every supported Python and Django
    nox -s "tests(3.13-django6.1)"           one combination
    nox -s browser                           the pages in a real browser
    nox -s messages                          the catalogues hold every marked string

CI runs these same sessions, built from the same table, so a check that
passes here passes there and a supported version cannot be left out of one.
Pythons that are not installed are fetched by uv.
"""

import os

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
    session.install('-e', '.[drf]', '--group', 'test', django_release(django))
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
    session.run('pytest', '-m', 'not browser', '--cov', '--cov-report=term', *session.posargs)


@nox.session(python=NEWEST_PYTHON)
def browser(session: nox.Session) -> None:
    """The pages in a real browser: the rule builder's script, and right to left."""
    session.install(
        '-e', '.[drf]', '--group', 'test', '--group', 'browser', django_release(NEWEST_DJANGO)
    )

    # A machine with a browser already says where (PLAYWRIGHT_BROWSERS_PATH); CI installs one.
    if not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
        session.run('python', '-m', 'playwright', 'install', '--with-deps', 'chromium')

    # Playwright drives the browser from an event loop; the test's own database calls are
    # made between its steps, never while a page is loading.
    session.run(
        'pytest', '-m', 'browser', *session.posargs, env={'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'}
    )


#: Each app with a catalogue, and the apps inside it its own catalogue leaves out.
CATALOGUES: dict[str, tuple[str, ...]] = {
    'src/clearance': ('roles', 'translations'),
    'src/clearance/roles': (),
    'src/clearance/translations': (),
}


@nox.session(python=NEWEST_PYTHON)
def messages(session: nox.Session) -> None:
    """
    The catalogues hold every string the library marks, and nothing it no
    longer marks: the strings are extracted again, and git finds no change.

    Needs gettext installed. After marking a string, run this, translate what
    it added, and compile: ``django-admin compilemessages`` in ``src/clearance``.
    """
    session.install('-e', '.[drf]', django_release(NEWEST_DJANGO))
    root = os.getcwd()

    for folder, inner in CATALOGUES.items():
        with session.chdir(folder):
            session.run(
                'python',
                '-m',
                'django',
                'makemessages',
                '--locale=fa',
                '--no-location',
                '--no-obsolete',
                '--ignore=__pycache__',
                *(f'--ignore={name}' for name in inner),
                '--settings=tests.project.settings',
                env={'PYTHONPATH': root},
            )

    session.run(
        'git',
        'diff',
        '--exit-code',
        '--ignore-matching-lines=POT-Creation-Date',
        '--',
        '*.po',
        external=True,
    )
