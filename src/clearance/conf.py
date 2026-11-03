"""
The ``CLEARANCE`` setting, read once and checked.

Every key lives in one dictionary in the project's settings::

    CLEARANCE = {
        'ROLES': 'accounts.roles.Role',
        'EVERY_ROW_ROLES': ['admin'],
    }

A key the library does not know is refused rather than ignored: a misspelled
``EVERY_ROWS_ROLES`` that is silently ignored is an administrator who sees no
rows, and nobody can tell why.

Values are worked out on first use and kept until Django says the setting
changed - so ``override_settings`` in a test reaches them, and a request does
not import and validate the same dotted path again.
"""

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, TypeVar

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from clearance.resolvers import RoleResolver

T = TypeVar('T')

#: Every key the setting may hold, and what it is when left out.
DEFAULTS: Final[Mapping[str, object]] = MappingProxyType(
    {
        'ROLES': None,
        'ROLE_RESOLVER': 'clearance.resolvers.AttributeResolver',
        'ROLE_ATTRIBUTE': 'role',
        'EVERY_ROW_ROLES': (),
        'STARTING_PERMISSIONS': None,
        'ROLE_GROUP_NAME': 'role:{role}',
    }
)


class ClearanceSettings:
    """The project's ``CLEARANCE`` setting, with defaults, validated on use."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # The values
    # ------------------------------------------------------------------

    @property
    def roles(self) -> tuple[str, ...]:
        """Every role the project declares, as codes."""
        return self._cached('roles', self._read_roles)

    @property
    def roles_declared(self) -> bool:
        """Whether ``ROLES`` is set at all - nothing else is asked of it."""
        return self.raw().get('ROLES') is not None

    @property
    def role_resolver(self) -> 'RoleResolver':
        """The resolver that says which roles a person has."""
        return self._cached('role_resolver', self._read_role_resolver)

    @property
    def role_attribute(self) -> str:
        """What ``AttributeResolver`` reads off a person."""
        return self._cached('role_attribute', self._read_role_attribute)

    @property
    def every_row_roles(self) -> frozenset[str]:
        """Roles that see every row of a queryset with no hook for them."""
        return self._cached('every_row_roles', self._read_every_row_roles)

    def reset(self) -> None:
        """Forget every value worked out, so the next use reads the setting again."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Reading and validating
    # ------------------------------------------------------------------

    def raw(self) -> Mapping[str, object]:
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

    def _value(self, key: str) -> object:
        return self.raw().get(key, DEFAULTS[key])

    def _cached(self, name: str, read: Callable[[], T]) -> T:
        if name not in self._cache:
            self._cache[name] = read()
        return self._cache[name]  # type: ignore[no-any-return]

    def _read_roles(self) -> tuple[str, ...]:
        value = self._value('ROLES')

        if value is None:
            raise ImproperlyConfigured(
                "CLEARANCE['ROLES'] is not set. "
                'Name a TextChoices of the roles, or list their codes.'
            )

        if isinstance(value, str):
            value = self._import(value, 'ROLES')

        codes = [str(code) for code in _values_of(value, 'ROLES')]

        if not codes:
            raise ImproperlyConfigured("CLEARANCE['ROLES'] declares no roles.")

        invalid = [code for code in codes if not code.isidentifier()]

        if invalid:
            raise ImproperlyConfigured(
                f"CLEARANCE['ROLES'] holds codes that cannot name a hook: {', '.join(invalid)}. "
                f'A role names scope_for_<role>, so it must be a valid Python identifier.'
            )

        repeated = sorted({code for code in codes if codes.count(code) > 1})

        if repeated:
            raise ImproperlyConfigured(
                f"CLEARANCE['ROLES'] declares {', '.join(repeated)} more than once."
            )

        return tuple(codes)

    def _read_role_resolver(self) -> 'RoleResolver':
        from clearance.resolvers import RoleResolver

        value = self._value('ROLE_RESOLVER')
        resolver_class = self._import(value, 'ROLE_RESOLVER') if isinstance(value, str) else value

        if not (isinstance(resolver_class, type) and issubclass(resolver_class, RoleResolver)):
            raise ImproperlyConfigured(
                f"CLEARANCE['ROLE_RESOLVER'] must name a subclass of RoleResolver, not {value!r}."
            )

        return resolver_class()

    def _read_role_attribute(self) -> str:
        value = self._value('ROLE_ATTRIBUTE')

        if not isinstance(value, str) or not value.isidentifier():
            raise ImproperlyConfigured(
                f"CLEARANCE['ROLE_ATTRIBUTE'] must be an attribute name, not {value!r}."
            )

        return value

    def _read_every_row_roles(self) -> frozenset[str]:
        roles = frozenset(
            str(code) for code in _values_of(self._value('EVERY_ROW_ROLES'), 'EVERY_ROW_ROLES')
        )
        undeclared = sorted(roles - set(self.roles))

        if undeclared:
            raise ImproperlyConfigured(
                f"CLEARANCE['EVERY_ROW_ROLES'] names roles ROLES does not declare: "
                f'{", ".join(undeclared)}.'
            )

        return roles

    @staticmethod
    def _import(path: str, key: str) -> object:
        try:
            return import_string(path)
        except ImportError as error:
            raise ImproperlyConfigured(
                f"CLEARANCE['{key}'] cannot import {path!r}: {error}"
            ) from error


def _values_of(value: object, key: str) -> Iterable[object]:
    """
    The codes in a ``TextChoices`` or in a list of them.

    A choices class iterates over its members; its ``values`` are the codes.
    A string is refused, because iterating one gives its letters.
    """
    values = getattr(value, 'values', value)

    if isinstance(values, str) or not isinstance(values, Iterable):
        raise ImproperlyConfigured(
            f"CLEARANCE['{key}'] must be a TextChoices or a list of codes, not {value!r}."
        )

    return values


#: The project's settings, as the library reads them.
clearance_settings = ClearanceSettings()


def _forget_on_change(*, setting: str, **kwargs: object) -> None:
    if setting == 'CLEARANCE':
        clearance_settings.reset()


setting_changed.connect(_forget_on_change)
