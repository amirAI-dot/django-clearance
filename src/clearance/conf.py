"""
The ``CLEARANCE`` setting, read and checked.

Every key lives in one dictionary in the project's settings, and the default
needs none of them::

    CLEARANCE = {
        'ACCESS': 'config.access.ACCESS',
        'SYNC_ON_MIGRATE': True,
    }

A key the library does not know is refused rather than ignored: a misspelled
``SYNC_ON_MIGRAT`` that is silently ignored is a deployment whose access
never changes, and nobody can tell why.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

#: Every key the setting may hold, and what it is when left out.
DEFAULTS: Final[Mapping[str, object]] = MappingProxyType(
    {
        'ROLE_RESOLVER': 'clearance.roles.resolvers.AssignmentResolver',
        'ROLE_ATTRIBUTE': 'role',
        'ACCESS': None,
        'SYNC_ON_MIGRATE': False,
        'RULE_DEPTH': 3,
    }
)


class ClearanceSettings:
    """The project's ``CLEARANCE`` setting, with defaults."""

    def raw(self) -> Mapping[str, object]:
        """The setting as written, refused when it is not a dictionary of known keys."""
        raw = getattr(settings, 'CLEARANCE', {})

        if not isinstance(raw, Mapping):
            raise ImproperlyConfigured('CLEARANCE must be a dictionary.')

        unknown = sorted(set(raw) - set(DEFAULTS))

        if unknown:
            raise ImproperlyConfigured(
                f'CLEARANCE has keys the library does not know: {", ".join(unknown)}. '
                f'It knows {", ".join(DEFAULTS)}.'
            )

        return raw

    def value(self, key: str) -> object:
        """``key`` as the project set it, or its default."""
        return self.raw().get(key, DEFAULTS[key])


#: The project's settings, as the library reads them.
clearance_settings = ClearanceSettings()
