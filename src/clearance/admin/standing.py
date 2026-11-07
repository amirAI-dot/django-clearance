"""
What the access pages show, worked out apart from how it is shown.

``Standing`` is one person's whole standing: their bundles, their own grants,
what was taken from them and why - and what they end up allowed, each
permission with where it came from. ``PermissionGrid`` is a bundle as the
administrator edits it: a model in each row, an action in each column, a
scope beside each tick.

Each is read in a fixed number of queries, however many models, bundles or
grants there are.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from django.contrib.auth.models import Group, Permission
from django.db.models import Model

from clearance.fields import Protection
from clearance.grants import Scope
from clearance.limits import limits
from clearance.models import PermissionRevocation, ScopeGrant, ScopeRule
from clearance.permissions import DEFAULT_ACTIONS, permission_for
from clearance.protocols import UserModel
from clearance.querysets import code_scopes

#: The columns of the grid: the four actions every model has.
COLUMNS: Final = DEFAULT_ACTIONS


def name_of(permission: Permission) -> str:
    """``app_label.codename``."""
    return f'{permission.content_type.app_label}.{permission.codename}'


# ---------------------------------------------------------------------- one person


@dataclass(frozen=True)
class Source:
    """Where a person's permission comes from: a bundle, or a grant to them."""

    bundle: Group | None
    scope: Scope
    #: Whether the bundle is one they start with by what they are - their role.
    starting: bool = False

    @property
    def direct(self) -> bool:
        return self.bundle is None


@dataclass
class Allowed:
    """A permission a person holds, with every source that gives it."""

    permission: Permission
    sources: list[Source] = field(default_factory=list)

    @property
    def name(self) -> str:
        return name_of(self.permission)


@dataclass
class Standing:
    """Everything about one person's access."""

    person: UserModel
    bundles: list[Group]
    direct: list[tuple[Permission, Scope]]
    revocations: list[PermissionRevocation]
    allowed: list[Allowed]
    #: What they are - their roles, with ``clearance.roles`` - in words.
    roles: list[str] = field(default_factory=list)
    #: The bundles they start with by what they are, not by being given them.
    starting: list[Group] = field(default_factory=list)
    #: What their bundles and grants give that their ceiling stops.
    stopped: list[Allowed] = field(default_factory=list)

    @property
    def superuser(self) -> bool:
        return bool(getattr(self.person, 'is_superuser', False))

    @classmethod
    def of(cls, person: UserModel) -> 'Standing':
        """Read in eight queries, however many bundles, grants and roles there are."""
        given = limits()
        bundles = list(person.groups.order_by('name'))
        starting = [
            bundle
            for bundle in given.starting_bundles(person).order_by('name')
            if bundle not in bundles
        ]
        every_bundle = [*bundles, *starting]
        through: Any = Group.permissions.through
        in_bundles = list(
            through.objects.filter(group__in=every_bundle).select_related(
                'permission__content_type', 'group'
            )
        )
        direct_permissions = list(person.user_permissions.select_related('content_type'))
        scopes = {
            (row.group_id, row.user_id, row.permission_id): row.scope
            for row in ScopeGrant.objects.filter(group__in=every_bundle)
            | ScopeGrant.objects.filter(user=person)
        }
        revocations = list(
            PermissionRevocation.objects.filter(user=person).select_related(
                'permission__content_type', 'revoked_by'
            )
        )
        revoked = {row.permission_id for row in revocations}
        starts = {bundle.pk for bundle in starting}

        direct = [
            (permission, scopes.get((None, person.pk, permission.pk)))
            for permission in direct_permissions
        ]
        held: dict[int, Allowed] = {}

        for row in in_bundles:
            if row.permission_id not in revoked:
                scope = scopes.get((row.group_id, None, row.permission_id))
                found = held.setdefault(row.permission_id, Allowed(row.permission))
                found.sources.append(Source(row.group, scope, row.group_id in starts))

        for permission, scope in direct:
            held.setdefault(permission.pk, Allowed(permission)).sources.append(Source(None, scope))

        within = set(
            Permission.objects.filter(pk__in=list(held))
            .filter(given.allowed(person, 'pk'))
            .values_list('pk', flat=True)
        )

        def ordered(items: Iterable[Allowed]) -> list[Allowed]:
            return sorted(items, key=lambda found: found.name)

        return cls(
            person,
            bundles,
            sorted(direct, key=lambda item: name_of(item[0])),
            revocations,
            ordered(found for pk, found in held.items() if pk in within),
            given.describe(person),
            starting,
            ordered(found for pk, found in held.items() if pk not in within),
        )


# ---------------------------------------------------------------------- a bundle as a grid


@dataclass
class Cell:
    """One permission in the grid: ticked or not, and the scope it is given with."""

    permission: Permission
    ticked: bool
    scope: Scope
    #: The scopes it may be given with - ``None`` for a field's, which takes none.
    scopes: Mapping[str, str] | None

    @property
    def name(self) -> str:
        return name_of(self.permission)

    @property
    def label(self) -> str:
        return str(self.permission.name)


@dataclass
class Row:
    """One model: a cell for each of the four actions it has, and the rest of its permissions."""

    model: type[Model]
    columns: list[Cell | None]
    others: list[Cell]

    @property
    def label(self) -> str:
        return f'{self.model._meta.app_config.verbose_name}: {self.model._meta.verbose_name_plural}'


class PermissionGrid:
    """Every permission there is, laid out as a bundle is edited."""

    columns = COLUMNS

    def __init__(self, rows: list[Row]) -> None:
        self.rows = rows

    @classmethod
    def build(cls, grants: Mapping[str, Scope]) -> 'PermissionGrid':
        """The grid, ticked where ``grants`` holds - read in three queries."""
        permissions = Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'
        )
        rules: dict[int, dict[str, str]] = {}

        for content_type, code, name in ScopeRule.objects.values_list(
            'content_type', 'code', 'name'
        ):
            rules.setdefault(content_type, {})[code] = name

        protection = Protection.load()
        by_model: dict[type[Model], list[Permission]] = {}

        for permission in permissions:
            model = permission.content_type.model_class()

            if model is not None:
                by_model.setdefault(model, []).append(permission)

        rows = [
            cls._row(model, found, grants, rules, protection) for model, found in by_model.items()
        ]
        return cls(rows)

    @staticmethod
    def parse(ticked: Iterable[str], scopes: Mapping[str, str]) -> dict[str, Scope]:
        """The grants a submitted grid holds: each ticked name, with its scope or none."""
        return {name: (scopes.get(name) or None) for name in ticked}

    @staticmethod
    def _row(
        model: type[Model],
        found: list[Permission],
        grants: Mapping[str, Scope],
        rules: Mapping[int, Mapping[str, str]],
        protection: Protection,
    ) -> Row:
        offered = {
            **{code: str(label) for code, label in code_scopes(model).items()},
            **rules.get(found[0].content_type_id, {}),
        }

        def cell(permission: Permission) -> Cell:
            name = name_of(permission)
            takes_scope = not protection.owns(model, name)
            return Cell(
                permission,
                name in grants,
                grants.get(name),
                offered if takes_scope else None,
            )

        by_name = {name_of(permission): permission for permission in found}
        column_names = [permission_for(model, action) for action in COLUMNS]
        columns = [cell(by_name[name]) if name in by_name else None for name in column_names]
        others = [
            cell(permission) for name, permission in by_name.items() if name not in column_names
        ]
        return Row(model, columns, others)
