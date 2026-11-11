"""
The example project starts, and its own tests pass, against the library as
it is now.

If this fails, the project people copy from does not run: a ``models.py``
that imports the library breaks when the user model is in the same app, the
DRF setting the documents recommend stops the project starting, or the
example teaches something the library no longer does.
"""

import os
import subprocess
import sys
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent / 'example'


def test_the_example_projects_own_tests_pass() -> None:
    environment = {
        key: value for key, value in os.environ.items() if key != 'DJANGO_SETTINGS_MODULE'
    }

    finished = subprocess.run(
        [sys.executable, 'manage.py', 'test', '--noinput'],
        cwd=EXAMPLE,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )

    assert finished.returncode == 0, finished.stdout + finished.stderr
