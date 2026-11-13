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
from typing import Final, cast

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
        'PERSON_FIELDS': (),
        'CASCADE_UNASKED_APPS': (),
    }
)

#: The keys that hold names - of fields, of apps - and nothing else.
_NAMES: Final = ('PERSON_FIELDS', 'CASCADE_UNASKED_APPS')


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

        self._check_rule_depth(raw.get('RULE_DEPTH', DEFAULTS['RULE_DEPTH']))

        for key in _NAMES:
            self._check_names(key, raw.get(key, DEFAULTS[key]))

        return raw

    def value(self, key: str) -> object:
        """``key`` as the project set it, or its default."""
        return self.raw().get(key, DEFAULTS[key])

    def rule_depth(self) -> int:
        """How many relations a rule may cross."""
        return cast(int, self.value('RULE_DEPTH'))  # raw() refuses anything else

    def person_fields(self) -> frozenset[str]:
        """
        The fields of the user model the project's code scopes read - ``branch``
        for "their branch". Like those a rule scope reads, nobody writes them on
        their own account: that would be changing their own access.
        """
        return frozenset(cast(tuple[str, ...], self.value('PERSON_FIELDS')))

    def cascade_unasked_apps(self) -> frozenset[str]:
        """
        The apps whose rows a delete takes with it unasked - an app keeping a
        token or an address for each account, whose ``delete`` nobody is given.
        A model the library guards is asked all the same.
        """
        return frozenset(cast(tuple[str, ...], self.value('CASCADE_UNASKED_APPS')))

    @staticmethod
    def _check_names(key: str, names: object) -> None:
        if not isinstance(names, list | tuple) or not all(isinstance(n, str) for n in names):
            raise ImproperlyConfigured(
                f'CLEARANCE[{key!r}] must be a list of names, not {names!r}.'
            )

    @staticmethod
    def _check_rule_depth(depth: object) -> None:
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
            raise ImproperlyConfigured(
                f"CLEARANCE['RULE_DEPTH'] must be a whole number from 1, not {depth!r}."
            )


#: The project's settings, as the library reads them.
clearance_settings = ClearanceSettings()
