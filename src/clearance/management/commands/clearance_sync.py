"""
``manage.py clearance_sync`` - make the database hold what the ``ACCESS`` file declares.

    clearance_sync --dry-run    what would change, writing nothing
    clearance_sync --check      in CI: fail when the database differs from the file
    clearance_sync              apply, and say what changed

Every change is listed before anything is written, and applied in one
transaction: a sync the safety rules refuse - one that would leave nobody
able to manage access - changes nothing.
"""

from typing import Any

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from clearance.declared import Sync, read_access
from clearance.safety import AccessRefused


class Command(BaseCommand):
    help = 'Make the database hold what the ACCESS file declares.'

    def add_arguments(self, parser: CommandParser) -> None:
        how = parser.add_mutually_exclusive_group()
        how.add_argument(
            '--dry-run', action='store_true', help='Say what would change; write nothing.'
        )
        how.add_argument(
            '--check', action='store_true', help='Fail when the database differs from the file.'
        )

    def handle(
        self, *args: Any, dry_run: bool = False, check: bool = False, **options: Any
    ) -> None:
        try:
            access = read_access()
        except ImproperlyConfigured as error:
            raise CommandError(str(error)) from None

        if access is None:
            raise CommandError("CLEARANCE['ACCESS'] names no file to sync.")

        sync = Sync(access)

        try:
            changes = sync.plan()
        except ValidationError as error:
            raise CommandError('\n'.join(['ACCESS cannot be applied:', *error.messages])) from None

        if not changes:
            self.stdout.write('The database holds what ACCESS declares.')
            return

        for change in changes:
            self.stdout.write(str(change))

        if check:
            raise CommandError(f'The database differs from ACCESS by {len(changes)} change(s).')

        if dry_run:
            self.stdout.write(f'{len(changes)} change(s); nothing was written.')
            return

        try:
            sync.apply(changes)
        except (AccessRefused, ValidationError) as error:
            messages = error.messages if isinstance(error, ValidationError) else [str(error)]
            raise CommandError('\n'.join(['Nothing was changed:', *messages])) from None

        self.stdout.write(self.style.SUCCESS(f'{len(changes)} change(s) applied.'))
