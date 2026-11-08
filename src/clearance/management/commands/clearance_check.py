"""
``manage.py clearance_check`` - what only the database can say is wrong.

Fails on an error - something made to give access that now gives none - and
lists warnings without failing, so it can stand in CI beside ``check``.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from clearance.health import ERROR, findings, unheld_permissions


class Command(BaseCommand):
    help = 'Say what the database holds that gives no access, or more than meant.'

    def handle(self, *args: Any, **options: Any) -> None:
        found = findings()

        for finding in found:
            style = self.style.ERROR if finding.level == ERROR else self.style.WARNING
            self.stdout.write(style(str(finding)))

        if options['verbosity'] >= 2:
            self.stdout.write(f'{unheld_permissions()} permission(s) nobody holds.')

        errors = sum(finding.level == ERROR for finding in found)

        if errors:
            raise CommandError(f'{errors} error(s) found.')

        if not found:
            self.stdout.write(self.style.SUCCESS('Nothing is wrong.'))
