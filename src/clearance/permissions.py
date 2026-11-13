"""
Declaring a resource's permissions, on its model.

A guarded resource declares its permissions in ``Meta.permissions``, so
``migrate`` creates the rows like any other permission and nothing has to be
synchronised::

    class Loan(models.Model):
        class Meta:
            default_permissions = ()
            permissions = build_permissions('loan', _('loans'), actions=('view', 'approve'))

``default_permissions = ()`` turns off Django's own add/change/delete/view,
which would otherwise sit beside these as a second answer to the same
question - one that no policy ever asks.

**A protected field has two permissions of its own** - one to read it, one to
write it - declared here (``protected_fields=('price',)``) or marked in the
database (``clearance.fields``). ``field_permission`` names them the way
``permission_for`` names a model's: ``shop.order_view_price`` for a model
declaring its own, ``shop.view_order_price`` for one keeping Django's.

**A status action is an action that writes values** - ``approve`` sets
``status`` to ``approved`` or ``rejected``, from ``pending`` - declared here
(``status_actions={...}``) or made in the database (``clearance.actions``).
Its permission is the action's, like any other.

**A model that declares nothing keeps Django's own permissions** -
``view_order``, ``add_order``, ``change_order``, ``delete_order`` - and
``permission_for`` answers in that style for it, so nothing anywhere spells a
permission's name by hand.

**The name written to the database is always English.** ``migrate`` stores it
in ``auth_permission.name`` once. A resource name marked for translation
would otherwise be resolved in whatever language was active when the model
was imported, baking it into the migration state - and ``makemigrations``
would then report changes on models nobody touched. So the stored name is
worked out with translation switched off, and the reader's language is
``PermissionSet.label``'s job.
"""

import re
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, Final, Self

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.utils import translation
from django.utils.functional import Promise, lazy
from django.utils.translation import gettext_lazy as _

#: The actions every guarded resource supports unless it says otherwise.
DEFAULT_ACTIONS: Final = ('view', 'create', 'edit', 'delete')

#: A record that is read, written and corrected, but never deleted. Offering
#: a ``delete`` permission on it would be a power that does nothing - shown in
#: every permission screen, granted to people, and refused by the policy.
RECORD_ACTIONS: Final = ('view', 'create', 'edit')

#: How an action reads, for the actions every resource has. Any other action
#: reads as its own words - ``look_up`` is "Can look up loans" - unless the
#: resource gives it a label of its own.
ACTION_LABELS: Final[Mapping[str, str | Promise]] = MappingProxyType(
    {
        'view': _('Can view %(resource)s'),
        'create': _('Can create %(resource)s'),
        'edit': _('Can edit %(resource)s'),
        'delete': _('Can delete %(resource)s'),
    }
)

#: How a protected field's two permissions read.
FIELD_LABELS: Final[Mapping[str, str | Promise]] = MappingProxyType(
    {
        'view': _('Can view %(field)s of %(resource)s'),
        'edit': _('Can edit %(field)s of %(resource)s'),
    }
)

#: What a status action declared in code says: the field, the values it
#: writes (``to``), and the values it may write them from (``from``, optional).
StatusDeclaration = Mapping[str, Any]

#: The two things a protected field's permissions allow.
FIELD_ACTIONS: Final = tuple(FIELD_LABELS)

#: A codename or an action: lowercase words joined by underscores. The
#: ``app_label.codename_action`` a policy asks for is built from these, and a
#: space or a dot in one would build a permission nobody can ever hold.
_NAME = re.compile(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*')


class DeclaredPermissions(tuple[tuple[str, str], ...]):
    """
    ``Meta.permissions`` as ``build_permissions`` makes it: the ``(codename,
    name)`` pairs Django reads, and what they were made from - the resource's
    codename and its protected fields - for the library to read back.
    """

    codename: str
    protected_fields: tuple[str, ...]
    status_actions: Mapping[str, StatusDeclaration]
    #: How each permission reads, ``{codename: label}``, in whatever language is active.
    labels: Mapping[str, Promise]

    def __new__(
        cls,
        entries: Iterable[tuple[str, str]],
        codename: str,
        protected_fields: Iterable[str] = (),
        status_actions: Mapping[str, StatusDeclaration] | None = None,
        labels: Mapping[str, Promise] | None = None,
    ) -> Self:
        declared = super().__new__(cls, entries)
        declared.codename = codename
        declared.protected_fields = tuple(protected_fields)
        declared.status_actions = MappingProxyType(dict(status_actions or {}))
        declared.labels = MappingProxyType(dict(labels or {}))
        return declared

    def adding(self, codename: str, label: Promise) -> 'DeclaredPermissions':
        """
        These, and one permission more that no action of the resource names -
        stored by its English name, as Django stores every permission's, and
        read in the reader's language.
        """
        with translation.override(None):
            stored = str(label)

        return DeclaredPermissions(
            [*self, (codename, stored)],
            self.codename,
            self.protected_fields,
            self.status_actions,
            {**self.labels, codename: label},
        )


class PermissionSet:
    """
    The permissions one resource declares: a codename, its actions and its
    protected fields.

    ``entries()`` is what goes in ``Meta.permissions``. The rest is for whoever
    reads a permission back - ``label`` says it in the reader's language.
    """

    def __init__(
        self,
        codename: str,
        resource: str | Promise,
        *,
        actions: Iterable[str] = DEFAULT_ACTIONS,
        labels: Mapping[str, str | Promise] | None = None,
        protected_fields: Iterable[str] = (),
        status_actions: Mapping[str, StatusDeclaration] | None = None,
    ) -> None:
        self.codename = codename
        self.resource = resource
        self.status_actions: Mapping[str, StatusDeclaration] = MappingProxyType(
            {
                code: _status_declaration(codename, code, raw)
                for code, raw in (status_actions or {}).items()
            }
        )
        declared = tuple(actions)
        self.actions = (*declared, *(code for code in self.status_actions if code not in declared))
        self.protected_fields = tuple(protected_fields)
        self.labels: Mapping[str, str | Promise] = MappingProxyType(
            {**ACTION_LABELS, **(labels or {})}
        )
        self._validate()

    def codename_for(self, action: str) -> str:
        """``view`` -> ``loan_view``."""
        return f'{self.codename}_{action}'

    def label(self, action: str) -> str:
        """How ``action`` reads in the active language."""
        template = self.labels.get(action)

        if template is None:
            words = action.replace('_', ' ')
            return f'Can {words} {self.resource}'

        return str(template) % {'resource': str(self.resource)}

    def stored_name(self, action: str) -> str:
        """How ``action`` reads in English: what ``migrate`` writes."""
        with translation.override(None):
            return self.label(action)

    def entries(self) -> DeclaredPermissions:
        """``(codename, name)`` for every action and protected field - ``Meta.permissions``."""
        actions = [(self.codename_for(action), self.stored_name(action)) for action in self.actions]
        fields = [
            (f'{self.codename}_{action}_{field}', field_label(action, field, self.resource))
            for field in self.protected_fields
            for action in FIELD_ACTIONS
        ]
        read = lazy(self.label, str)
        read_field = lazy(_field_words, str)
        labels: dict[str, Any] = {  # lazy: each reads in the language active when read
            **{self.codename_for(action): read(action) for action in self.actions},
            **{
                f'{self.codename}_{action}_{field}': read_field(action, field, self.resource)
                for field in self.protected_fields
                for action in FIELD_ACTIONS
            },
        }
        return DeclaredPermissions(
            [*actions, *fields], self.codename, self.protected_fields, self.status_actions, labels
        )

    def _validate(self) -> None:
        if not _NAME.fullmatch(self.codename):
            raise ImproperlyConfigured(
                f'{self.codename!r} is not a codename: use lowercase words joined by underscores.'
            )

        if not self.actions:
            raise ImproperlyConfigured(f'{self.codename!r} declares no actions.')

        for action in self.actions:
            if not _NAME.fullmatch(action):
                raise ImproperlyConfigured(
                    f'{action!r} is not an action: use lowercase words joined by underscores.'
                )

        repeated = sorted({action for action in self.actions if self.actions.count(action) > 1})

        if repeated:
            raise ImproperlyConfigured(
                f'{self.codename!r} declares {", ".join(repeated)} more than once.'
            )

        unknown = sorted(set(self.labels) - set(ACTION_LABELS) - set(self.actions))

        if unknown:
            raise ImproperlyConfigured(
                f'{self.codename!r} labels actions it does not declare: {", ".join(unknown)}.'
            )

        self._validate_fields()

    def _validate_fields(self) -> None:
        for field in self.protected_fields:
            if not _NAME.fullmatch(field):
                raise ImproperlyConfigured(
                    f'{field!r} is not a field name: use lowercase words joined by underscores.'
                )

        repeated = sorted({f for f in self.protected_fields if self.protected_fields.count(f) > 1})

        if repeated:
            raise ImproperlyConfigured(
                f'{self.codename!r} protects {", ".join(repeated)} more than once.'
            )

        clashing = sorted(
            f'{action}_{field}'
            for field in self.protected_fields
            for action in FIELD_ACTIONS
            if f'{action}_{field}' in self.actions
        )

        if clashing:
            raise ImproperlyConfigured(
                f'{self.codename!r} declares {", ".join(clashing)} both as an action and as '
                f'the permission of a protected field.'
            )


def build_permissions(
    codename: str,
    resource: str | Promise,
    *,
    actions: Iterable[str] = DEFAULT_ACTIONS,
    labels: Mapping[str, str | Promise] | None = None,
    protected_fields: Iterable[str] = (),
    status_actions: Mapping[str, StatusDeclaration] | None = None,
) -> DeclaredPermissions:
    """
    ``Meta.permissions`` for one resource.

    ``build_permissions('loan', 'loans')`` gives ``loan_view``, ``loan_create``,
    ``loan_edit`` and ``loan_delete``. ``labels`` names an action in words of
    its own - ``{'approve': _('Can approve or decline %(resource)s')}``.
    ``protected_fields=('rate',)`` adds ``loan_view_rate`` and ``loan_edit_rate``.
    ``status_actions={'approve': {'field': 'status', 'to': ['approved']}}``
    adds the action ``approve``, which alone writes ``approved``.
    """
    return PermissionSet(
        codename,
        resource,
        actions=actions,
        labels=labels,
        protected_fields=protected_fields,
        status_actions=status_actions,
    ).entries()


def field_label(action: str, field: str | Promise, resource: str | Promise) -> str:
    """How a protected field's permission reads in English - what is stored."""
    with translation.override(None):
        return _field_words(action, field, resource)


def _field_words(action: str, field: str | Promise, resource: str | Promise) -> str:
    """How a protected field's permission reads in the active language."""
    words = str(field).replace('_', ' ')
    return str(FIELD_LABELS[action]) % {'field': words, 'resource': str(resource)}


def declared_label(model: type[Model], codename: str) -> str | None:
    """How ``build_permissions`` says ``codename`` reads, in the active language - or ``None``."""
    declared = model._meta.permissions
    label = declared.labels.get(codename) if isinstance(declared, DeclaredPermissions) else None
    return str(label) if label is not None else None


def is_action_name(name: object) -> bool:
    """Whether ``name`` can end a permission's codename: lowercase words joined by underscores."""
    return isinstance(name, str) and _NAME.fullmatch(name) is not None


#: Django's own verb for each of the four actions every model has.
DJANGO_VERBS: Final[Mapping[str, str]] = MappingProxyType(
    {'view': 'view', 'create': 'add', 'edit': 'change', 'delete': 'delete'}
)


def permission_for(model: type[Model] | Model, action: str, *, codename: str | None = None) -> str:
    """
    The permission ``action`` on ``model`` needs, as ``app_label.codename``.

    A model keeping Django's permissions answers in Django's style -
    ``shop.change_order`` for ``edit``; a model that declares its own answers
    in the library's - ``shop.order_edit``. Listing is viewing. An action
    beyond the four is ``<codename>_<action>`` either way. ``codename`` names
    the resource when it is not the model's own name.
    """
    meta = model._meta
    action = 'view' if action == 'list' else action
    verb = DJANGO_VERBS.get(action)

    if verb is not None and verb in meta.default_permissions:
        return f'{meta.app_label}.{verb}_{meta.model_name}'

    return f'{meta.app_label}.{codename or meta.model_name}_{action}'


def field_permission(model: type[Model] | Model, field: str, action: str) -> str:
    """
    The permission reading (``view``) or writing (``edit``) ``field`` of
    ``model`` needs, as ``app_label.codename``.

    ``shop.order_view_price`` on a model declaring its own permissions,
    ``shop.view_order_price`` - Django's verbs - on one keeping Django's.

    It is the permission of the model the field is a field *of*: asked about
    a proxy, or a model that inherits the field from a parent with a table of
    its own, the answer is the one model's that declares it - a field has two
    permissions, however many models show it.
    """
    if action not in FIELD_ACTIONS:
        raise ValueError(f'A field is read with view or written with edit, not {action!r}.')

    model = field_owner(model, field)
    meta = model._meta
    verb = DJANGO_VERBS[action]

    if verb in meta.default_permissions:
        return f'{meta.app_label}.{verb}_{meta.model_name}_{field}'

    return f'{meta.app_label}.{resource_codename(model)}_{action}_{field}'


def field_owner(model: type[Model] | Model, field: str) -> type[Model]:
    """
    The model ``field`` is a field of: ``model``'s concrete model - never a
    proxy - or the parent it is inherited from, when that has its own table.
    """
    from django.core.exceptions import FieldDoesNotExist

    concrete: type[Model] = model._meta.concrete_model  # type: ignore[assignment]

    try:
        owner = getattr(concrete._meta.get_field(field), 'model', None)
    except FieldDoesNotExist:
        return concrete

    # A relation another model has to this one answers with that model: not an owner.
    return owner if isinstance(owner, type) and issubclass(concrete, owner) else concrete


def models_of(model: type[Model] | Model) -> tuple[type[Model], ...]:
    """
    Every model whose fields ``model`` has: its concrete model, and the
    parents it inherits from that have tables of their own.
    """
    concrete: type[Model] = model._meta.concrete_model  # type: ignore[assignment]
    return (concrete, *concrete._meta.get_parent_list())


def resource_codename(model: type[Model] | Model) -> str:
    """The codename ``model``'s permissions are built from: ``build_permissions``', or its name."""
    declared = model._meta.permissions
    codename = declared.codename if isinstance(declared, DeclaredPermissions) else None
    return codename or str(model._meta.model_name)


def declared_status_actions(model: type[Model] | Model) -> Mapping[str, StatusDeclaration]:
    """
    The status actions ``model`` declares in code, through ``build_permissions``
    - its concrete model's: a proxy writes the same rows, so the same values
    are claimed on it.
    """
    declared = model._meta.concrete_model._meta.permissions  # type: ignore[union-attr]
    return declared.status_actions if isinstance(declared, DeclaredPermissions) else {}


def _status_declaration(codename: str, code: str, raw: object) -> StatusDeclaration:
    """``raw``, checked for shape - the model checks its field and values at start-up (E015)."""
    where = f'{codename!r} declares the status action {code!r}'

    if not isinstance(raw, Mapping) or set(raw) - {'field', 'to', 'from'}:
        raise ImproperlyConfigured(f"{where}: give it 'field', 'to' and optionally 'from'.")

    field, to, start = raw.get('field'), raw.get('to'), raw.get('from', ())

    if not isinstance(field, str) or not field:
        raise ImproperlyConfigured(f'{where}: name its field.')

    if not isinstance(to, list | tuple) or not to:
        raise ImproperlyConfigured(f"{where}: 'to' is a list of the values it writes.")

    if not isinstance(start, list | tuple):
        raise ImproperlyConfigured(f"{where}: 'from' is a list of values.")

    return MappingProxyType({'field': field, 'to': tuple(to), 'from': tuple(start)})


def declared_protected_fields(model: type[Model] | Model) -> tuple[str, ...]:
    """
    The fields of ``model`` protected in code, through ``build_permissions`` -
    on its concrete model, or on a parent it inherits them from. A proxy shows
    the same columns, so what is protected on the model is protected on it.
    """
    found: list[str] = []

    for owner in models_of(model):
        declared = owner._meta.permissions

        if isinstance(declared, DeclaredPermissions):
            found += [name for name in declared.protected_fields if name not in found]

    return tuple(found)
