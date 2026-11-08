"""
The ``roles`` section of the ``ACCESS`` file - registered when the app starts::

    'roles': {
        'customer': {
            'name': 'Customer',                         # the code, readable, if left out
            'ceiling': ['shop.view_order', 'shop.add_order'],   # None: no ceiling
            'bundles': ['Customers'],                   # its starting bundles
        },
    }

A ceiling left out permits nothing, as a new role's does. A starting bundle
may be one the file declares, or one made in the admin site. Who has a role
is not the file's to say.
"""

from collections.abc import Callable, Mapping
from typing import Any

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from clearance.declared import Access, Change, Section
from clearance.permissions import is_action_name
from clearance.roles.models import Role
from clearance.roles.services import RoleService
from clearance.services import AccessService


class RoleSection(Section):
    name = 'roles'
    kind = 'role'

    def problems(self, declared: Any, access: Access) -> list[str]:
        if not isinstance(declared, Mapping):
            return ['is a dictionary of role codes to roles.']

        problems = []

        for code, spec in declared.items():
            if not is_action_name(code):
                problems.append(f'{code!r} is not a code: use lowercase words joined by _.')
            elif not isinstance(spec, Mapping) or set(spec) - {'name', 'ceiling', 'bundles'}:
                problems.append(f"{code!r}: give it 'name', 'ceiling' and 'bundles'.")
            elif not isinstance(spec.get('ceiling', []), list | tuple | type(None)):
                problems.append(f"{code!r}: 'ceiling' is a list of permissions, or None.")
            elif not isinstance(spec.get('bundles', []), list | tuple):
                problems.append(f"{code!r}: 'bundles' is a list of bundle names.")

        return problems

    def changes(self, declared: Any, access: Access) -> tuple[list[Change], list[Change]]:
        service = RoleService(actor=None)
        file_bundles = set(access.get('bundles', {}))
        owned = self.owned()
        problems: list[str] = []
        made: list[Change] = []

        for code, spec in declared.items():
            wanted = _spec(code, spec)
            missing = [
                name
                for name in wanted['bundles']
                if name not in file_bundles and not Group.objects.filter(name=name).exists()
            ]
            problems += [f'role {code!r}: there is no bundle {name!r}' for name in missing]

            try:
                AccessService(actor=None).check_grants(dict.fromkeys(wanted['ceiling'] or ()))
            except ValidationError as error:
                problems += [f'role {code!r}: {message}' for message in error.messages]

            role = Role.objects.filter(code=code).first()

            if role is None:
                made.append(Change('+', self.kind, code, _lines(None, wanted), self._make(wanted)))
                continue

            before = {
                'name': role.name,
                'ceiling': service.ceiling_of(role),
                'bundles': frozenset(role.bundles.values_list('group__name', flat=True)),
            }

            if before != {key: wanted[key] for key in before} or code not in owned:
                details = _lines(before, wanted)
                if code not in owned:
                    details += ('now declared in code',)
                made.append(
                    Change('~', self.kind, code, details, self._change(role, before, wanted))
                )

        if problems:
            raise ValidationError(problems)

        gone = sorted(owned - set(declared))
        return made, [Change('-', self.kind, code, (), self._delete(code)) for code in gone]

    def _make(self, wanted: dict[str, Any]) -> Callable[[], None]:
        def make() -> None:
            RoleService(actor=None).create_role(
                wanted['code'],
                wanted['name'],
                ceiling=wanted['ceiling'],
                bundles=list(Group.objects.filter(name__in=wanted['bundles'])),
            )
            self.own(wanted['code'])

        return make

    def _change(
        self, role: Role, before: dict[str, Any], wanted: dict[str, Any]
    ) -> Callable[[], None]:
        def change() -> None:
            service = RoleService(actor=None)
            service.rename_role(role, wanted['name'])
            service.set_ceiling(role, wanted['ceiling'])

            for name in wanted['bundles'] - before['bundles']:
                service.give_bundle(role, Group.objects.get(name=name))
            for name in before['bundles'] - wanted['bundles']:
                service.take_bundle(role, Group.objects.get(name=name))

            self.own(role.code)

        return change

    def _delete(self, code: str) -> Callable[[], None]:
        def delete() -> None:
            role = Role.objects.filter(code=code).first()
            if role is not None:
                RoleService(actor=None).delete_role(role)
            self.disown(code)

        return delete


def _spec(code: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    ceiling = spec.get('ceiling', [])
    return {
        'code': code,
        'name': str(spec.get('name') or code.replace('_', ' ').capitalize()),
        'ceiling': None if ceiling is None else frozenset(ceiling),
        'bundles': frozenset(spec.get('bundles', ())),
    }


def _lines(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> tuple[str, ...]:
    def ceiling(value: frozenset[str] | None) -> str:
        return 'none' if value is None else ', '.join(sorted(value)) or 'nothing'

    if before is None:
        return (
            f'ceiling: {ceiling(after["ceiling"])}',
            f'bundles: {", ".join(sorted(after["bundles"])) or "none"}',
        )

    lines = []
    if before['name'] != after['name']:
        lines.append(f'name: {before["name"]!r} -> {after["name"]!r}')
    if before['ceiling'] != after['ceiling']:
        lines.append(f'ceiling: {ceiling(before["ceiling"])} -> {ceiling(after["ceiling"])}')
    if before['bundles'] != after['bundles']:
        lines.append(
            f'bundles: {", ".join(sorted(before["bundles"])) or "none"} -> '
            f'{", ".join(sorted(after["bundles"])) or "none"}'
        )
    return tuple(lines)
