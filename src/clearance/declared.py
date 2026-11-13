"""
Access written as code - the ``ACCESS`` file - compared with the database,
and applied by ``clearance_sync``.

    # config/access.py - CLEARANCE = {'ACCESS': 'config.access.ACCESS'}
    ACCESS = {
        'bundles': {
            'Branch managers': {'shop.view_order': 'branch', 'shop.order_approve': 'branch'},
        },
        'status_actions': {
            'shop.Order': {
                'approve': {'field': 'status', 'to': ['approved'], 'from': ['pending']},
            },
        },
        'roles': {                       # with clearance.roles installed
            'manager': {'name': 'Manager', 'ceiling': None, 'bundles': ['Branch managers']},
        },
    }

**The file owns what it names, and nothing else.** A sync makes what the
file adds, changes what it changes, and deletes what it once named and names
no more - the ``Declared`` rows say which is which. A bundle, role or status
action made in the admin site is never touched unless the file comes to
name it; then the file owns it from that sync on. What the file owns is read
only in the admin site.

A sync is one transaction, through the same services the admin site uses -
as the system, so the rules about who may do what do not apply, but the one
about leaving somebody able to manage access does. Who is given a bundle or
a role is not the file's business: that stays in the admin site.

Each part of the file is a ``Section``: the core reads ``bundles`` and
``status_actions``, and ``clearance.roles`` adds ``roles`` when it is
installed - the core never imports it.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from django.apps import apps
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.utils.module_loading import import_string

from clearance.actions import status_action_problems, transition
from clearance.conf import clearance_settings
from clearance.grants import Scope
from clearance.models import Declared, StatusAction
from clearance.services import AccessService

#: The file, as written: a section's name, and what it declares.
Access = Mapping[str, Any]


@dataclass(frozen=True)
class Change:
    """One change a sync would make: ``+`` made, ``~`` changed, ``-`` deleted."""

    verb: str
    kind: str
    key: str
    details: tuple[str, ...] = ()
    apply: Callable[[], None] = field(default=lambda: None, compare=False, repr=False)

    def __str__(self) -> str:
        head = f'{self.verb} {self.kind.replace("_", " ")} {self.key!r}'
        return '\n'.join([head, *(f'    {detail}' for detail in self.details)])


class Section(ABC):
    """One part of the ``ACCESS`` file: what it may say, and what it changes."""

    #: The key in the file.
    name: ClassVar[str]
    #: What ``Declared`` calls what it owns.
    kind: ClassVar[str]

    @abstractmethod
    def problems(self, declared: Any, access: Access) -> list[str]:
        """What is wrong with it, said without the database - for E001."""

    @abstractmethod
    def changes(self, declared: Any, access: Access) -> tuple[list[Change], list[Change]]:
        """
        What a sync would make and change, and what it would delete - checked
        against the database, or a ``ValidationError`` naming every problem.
        """

    def owned(self) -> set[str]:
        return Declared.keys(self.kind)

    def own(self, key: str) -> None:
        Declared.objects.get_or_create(kind=self.kind, key=key)

    def disown(self, key: str) -> None:
        Declared.objects.filter(kind=self.kind, key=key).delete()


#: Every section the file may have, in the order a sync makes and changes them.
SECTIONS: dict[str, Section] = {}


def register_section(section: Section) -> None:
    """Let the file have ``section`` - a layer above the core adds its own."""
    SECTIONS[section.name] = section


# ---------------------------------------------------------------------- the file


def read_access() -> Access | None:
    """The file ``CLEARANCE['ACCESS']`` names, or ``None`` when it names none."""
    path = clearance_settings.value('ACCESS')

    if path is None:
        return None

    try:
        access = import_string(str(path))
    except ImportError as error:
        raise ImproperlyConfigured(f"CLEARANCE['ACCESS'] cannot be read: {error}") from None

    if not isinstance(access, Mapping):
        raise ImproperlyConfigured(f"CLEARANCE['ACCESS'] {path!r} is not a dictionary.")

    unknown = sorted(set(access) - set(SECTIONS))

    if unknown:
        raise ImproperlyConfigured(
            f'ACCESS has sections no installed app reads: {", ".join(unknown)}. '
            f'It may have {", ".join(SECTIONS)}.'
        )

    return access


def access_problems(access: Access) -> list[str]:
    """Everything wrong with ``access`` that can be told without the database."""
    return [
        f'{name}: {problem}'
        for name, section in SECTIONS.items()
        if name in access
        for problem in section.problems(access[name], access)
    ]


class Sync:
    """``access`` compared with the database, and applied."""

    def __init__(self, access: Access) -> None:
        self.access = access

    def plan(self) -> list[Change]:
        """Every change, in the order it is made - or a ``ValidationError`` naming every problem."""
        problems = access_problems(self.access)

        if problems:
            raise ValidationError(problems)

        made: list[Change] = []
        deleted: list[Change] = []

        for name, section in SECTIONS.items():
            upserts, deletions = section.changes(self.access.get(name, {}), self.access)
            made += upserts
            deleted = deletions + deleted  # deleted in the reverse order they were made

        return made + deleted

    def apply(self, changes: Iterable[Change] | None = None) -> list[Change]:
        """Make every change in one transaction; the changes made."""
        planned = self.plan() if changes is None else list(changes)

        with transaction.atomic():
            for change in planned:
                change.apply()

        return planned


# ---------------------------------------------------------------------- bundles


class BundleSection(Section):
    """``{'bundle name': {'app_label.codename': 'scope' or None}}``."""

    name = 'bundles'
    kind = 'bundle'

    def problems(self, declared: Any, access: Access) -> list[str]:
        if not isinstance(declared, Mapping):
            return ['is a dictionary of bundle names to their grants.']

        problems = []

        for bundle, grants in declared.items():
            if not isinstance(bundle, str) or not bundle.strip():
                problems.append(f'{bundle!r} is not a bundle name.')
            elif not isinstance(grants, Mapping):
                problems.append(f'{bundle!r} is a dictionary of permissions to scopes.')
            else:
                problems += [f'{bundle!r}: {problem}' for problem in _grant_problems(grants)]

        return problems

    def changes(self, declared: Any, access: Access) -> tuple[list[Change], list[Change]]:
        service = AccessService(actor=None)
        existing = {group.name: group for group in Group.objects.filter(name__in=list(declared))}
        owned = self.owned()
        problems: list[str] = []
        made: list[Change] = []

        for name, grants in declared.items():
            wanted = dict(grants)

            try:
                service.check_grants(wanted)
            except ValidationError as error:
                problems += [f'bundle {name!r}: {message}' for message in error.messages]
                continue

            group = existing.get(name)

            if group is None:
                made.append(
                    Change('+', self.kind, name, _grant_lines({}, wanted), self._make(name, wanted))
                )
                continue

            before = service.bundle_grants(group)
            adopting = name not in owned

            if before != wanted or adopting:
                details = _grant_lines(before, wanted)
                if adopting:
                    details += ('now declared in code',)
                made.append(Change('~', self.kind, name, details, self._change(group, wanted)))

        if problems:
            raise ValidationError(problems)

        gone = sorted(owned - set(declared))
        return made, [Change('-', self.kind, name, (), self._delete(name)) for name in gone]

    def _make(self, name: str, grants: dict[str, Scope]) -> Callable[[], None]:
        def make() -> None:
            AccessService(actor=None).create_bundle(name, grants)
            self.own(name)

        return make

    def _change(self, group: Group, grants: dict[str, Scope]) -> Callable[[], None]:
        def change() -> None:
            AccessService(actor=None).change_bundle(group, grants=grants)
            self.own(group.name)

        return change

    def _delete(self, name: str) -> Callable[[], None]:
        def delete() -> None:
            group = Group.objects.filter(name=name).first()
            if group is not None:
                AccessService(actor=None).delete_bundle(group)
            self.disown(name)

        return delete


# ---------------------------------------------------------------------- status actions


class StatusActionSection(Section):
    """``{'app_label.Model': {'code': {'field': ..., 'to': [...], 'from': [...]}}}``."""

    name = 'status_actions'
    kind = 'status_action'

    def problems(self, declared: Any, access: Access) -> list[str]:
        if not isinstance(declared, Mapping):
            return ['is a dictionary of models to their status actions.']

        problems = []

        for label, actions in declared.items():
            model = _model(label)

            if model is None:
                problems.append(f'{label!r} is not an installed model.')
            elif not isinstance(actions, Mapping):
                problems.append(f'{label!r} is a dictionary of codes to status actions.')
            else:
                for code, spec in actions.items():
                    problems += [
                        f'{label}.{code}: {problem}'
                        for problem in _status_problems(model, code, spec)
                    ]

        return problems

    def changes(self, declared: Any, access: Access) -> tuple[list[Change], list[Change]]:
        owned = self.owned()
        made: list[Change] = []
        problems: list[str] = []
        named: set[str] = set()

        for label, actions in declared.items():
            model = _model(label)
            assert model is not None  # problems() refused any other
            content_type = ContentType.objects.get_for_model(model)

            for code, spec in actions.items():
                key = f'{model._meta.label}.{code}'
                named.add(key)
                wanted = _status_spec(code, spec)
                row = StatusAction.objects.filter(content_type=content_type, code=code).first()

                if row is None:
                    made.append(
                        Change(
                            '+',
                            self.kind,
                            key,
                            _status_lines(None, wanted),
                            self._make(model, key, wanted),
                        )
                    )
                    continue

                if row.field != wanted['field']:
                    problems.append(
                        f'status action {key!r} writes {row.field!r}, not {wanted["field"]!r}: '
                        f'a status action keeps its field - give it a new code.'
                    )
                    continue

                before = _status_spec(
                    code,
                    {
                        'field': row.field,
                        'to': row.to_values,
                        'from': row.from_values,
                        'name': row.name,
                    },
                )
                same = transition(
                    model, code, row.field, before['to'], before['from']
                ) == transition(model, code, row.field, wanted['to'], wanted['from'])

                if not same or before['name'] != wanted['name'] or key not in owned:
                    details = _status_lines(before, wanted)
                    if key not in owned:
                        details += ('now declared in code',)
                    made.append(
                        Change('~', self.kind, key, details, self._change(row, key, wanted))
                    )

        if problems:
            raise ValidationError(problems)

        gone = sorted(owned - named)
        return made, [Change('-', self.kind, key, (), self._delete(key)) for key in gone]

    def _make(self, model: Any, key: str, spec: dict[str, Any]) -> Callable[[], None]:
        def make() -> None:
            AccessService(actor=None).create_status_action(
                model, spec['code'], spec['name'], spec['field'], spec['to'], spec['from']
            )
            self.own(key)

        return make

    def _change(self, row: StatusAction, key: str, spec: dict[str, Any]) -> Callable[[], None]:
        def change() -> None:
            AccessService(actor=None).change_status_action(
                row, name=spec['name'], to=spec['to'], start=spec['from']
            )
            self.own(key)

        return change

    def _delete(self, key: str) -> Callable[[], None]:
        def delete() -> None:
            label, _, code = key.rpartition('.')
            model = _model(label)
            row = (
                StatusAction.objects.filter(
                    content_type=ContentType.objects.get_for_model(model), code=code
                ).first()
                if model is not None
                else None
            )
            if row is not None:
                AccessService(actor=None).delete_status_action(row)
            self.disown(key)

        return delete


register_section(BundleSection())
register_section(StatusActionSection())


# ---------------------------------------------------------------------- on migrate


def sync_after_migrate(
    sender: Any,
    using: str = DEFAULT_DB_ALIAS,
    plan: Any = None,
    verbosity: int = 1,
    **kwargs: Any,
) -> None:
    """
    ``post_migrate``, with ``SYNC_ON_MIGRATE``: apply the file once a forward
    ``migrate`` of the default database has finished - after the last app, so
    every permission it names exists - and never on a test database.
    """
    if not clearance_settings.value('SYNC_ON_MIGRATE'):
        return

    last = list(apps.get_app_configs())[-1]
    backwards = any(backward for _, backward in plan or ())

    if sender is not last or using != DEFAULT_DB_ALIAS or backwards:
        return

    if is_test_database(using):
        if verbosity >= 1:
            # Told by its name: a working database called test_... would never sync, unsaid.
            name = connections[using].settings_dict.get('NAME')
            print(f'clearance_sync: skipped on {name!r}, a database made for tests.')
        return

    access = read_access()

    if access is None:
        return

    changes = Sync(access).apply()

    if verbosity >= 1:
        print(f'clearance_sync: {len(changes)} change(s) applied from ACCESS.')


def is_test_database(using: str) -> bool:
    """Whether ``using`` is a database made for tests - by its name, as Django names them."""
    connection = connections[using]
    name = str(connection.settings_dict.get('NAME') or '')
    test_name = connection.settings_dict.get('TEST', {}).get('NAME')
    in_memory = name.startswith('file:memorydb_') or name == ':memory:'
    return in_memory or name.startswith('test_') or (bool(test_name) and name == test_name)


# ---------------------------------------------------------------------- helpers


def _grant_problems(grants: Mapping[Any, Any]) -> list[str]:
    problems = []

    for permission, scope in grants.items():
        app_label, dot, codename = str(permission).partition('.')

        if not dot or not codename:
            problems.append(f'{permission!r} is not app_label.codename.')
        elif app_label not in {config.label for config in apps.get_app_configs()}:
            problems.append(f'{permission!r} names no installed app.')

        if scope is not None and not isinstance(scope, str):
            problems.append(f'{permission!r}: a scope is a name, or None.')

    return problems


def _grant_lines(before: Mapping[str, Scope], after: Mapping[str, Scope]) -> tuple[str, ...]:
    def scope(value: Scope) -> str:
        return value or "the model's default"

    lines = [f'+ {name} ({scope(after[name])})' for name in sorted(set(after) - set(before))]
    lines += [f'- {name}' for name in sorted(set(before) - set(after))]
    lines += [
        f'~ {name}: {scope(before[name])} -> {scope(after[name])}'
        for name in sorted(set(before) & set(after))
        if before[name] != after[name]
    ]
    return tuple(lines)


def _model(label: Any) -> Any:
    try:
        return apps.get_model(str(label))
    except (LookupError, ValueError):
        return None


def _status_spec(code: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'code': code,
        'name': str(spec.get('name') or code.replace('_', ' ').capitalize()),
        'field': spec.get('field'),
        'to': list(spec.get('to') or ()),
        'from': list(spec.get('from') or ()),
    }


def _status_problems(model: Any, code: Any, spec: Any) -> list[str]:
    if not isinstance(spec, Mapping) or set(spec) - {'field', 'to', 'from', 'name'}:
        return ["give it 'field', 'to', and optionally 'from' and 'name'."]

    if not isinstance(spec.get('field'), str):
        return ["'field' is the name of a field."]

    for end in ('to', 'from'):
        if not isinstance(spec.get(end, []), list | tuple):
            return [f'{end!r} is a list of values.']

    wanted = _status_spec(str(code), spec)
    return status_action_problems(
        model, str(code), str(wanted['field']), wanted['to'], wanted['from']
    )


def _status_lines(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> tuple[str, ...]:
    if before is None:
        return (f'{after["field"]} -> {", ".join(map(str, after["to"]))}',)

    lines = []
    for key in ('name', 'to', 'from'):
        if before[key] != after[key]:
            lines.append(f'{key}: {before[key]!r} -> {after[key]!r}')
    return tuple(lines)
