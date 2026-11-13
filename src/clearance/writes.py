"""
What a person may not write, out of the values they sent.

    refused_writes(user, Loan, {'amount': 5, 'status': 'approved'}, loan)
    # {'status': 'You may not set status to approved.'}

A protected field they may not write is refused whatever its value; a value a
status action claims is refused to whoever is not allowed the action, from
where the row stands. Keys that are not fields of the model are left alone -
they are the serializer's or the form's to judge.

Every door that takes values from outside asks this - the API's permission
class and its serializers - so a value is refused the same way whichever
door it came through, and the refusal names the field.

**And what is written stays among the rows the person reaches.** A scope that
only narrowed what is read would let somebody given "their own" create a row
for anybody else, or move a row to where they could never have reached it.
So every door asks, once the row is saved and inside the same transaction::

    with transaction.atomic():
        payment = form.save()
        require_within_scope(request.user, 'create', payment)

A row outside the scope the action was given in is refused, and the
transaction it was written in is undone. The library's views, serializers
and admin pages ask by themselves; a view of the project's own that saves by
hand asks as above.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import router
from django.db.models import Model
from django.db.models.deletion import Collector
from django.utils.translation import gettext_lazy as _

from clearance.actions import clean_value, status_actions_of, writable_values
from clearance.fields import writable_fields
from clearance.permissions import DeclaredPermissions
from clearance.protocols import User
from clearance.querysets import ScopedQuerySet, visible
from clearance.registry import registry

#: The actions that only look: a write made by a view of one is an edit.
_READS = frozenset({'view', 'list'})


def refused_writes(
    user: User, model: type[Model], data: Mapping[str, Any], obj: Model | None = None
) -> dict[str, str]:
    """``{field: why}`` for every value in ``data`` ``user`` may not write to ``obj``."""
    # A relation is written under its column's name too - ``officer_id`` for ``officer``.
    names = {
        key: field.name
        for field in (*model._meta.fields, *model._meta.many_to_many)
        for key in (field.name, field.attname)
    }
    sent = {names[key]: value for key, value in data.items() if key in names}

    if not sent:
        return {}

    writable = writable_fields(user, model)
    status_fields = status_actions_of(user).fields(model)
    refused: dict[str, str] = {}

    for name, value in sent.items():
        if name not in writable:
            refused[name] = str(_('You may not write %(field)s.') % {'field': name})
        elif name in status_fields:
            cleaned = clean_value(model, name, value)

            if cleaned not in writable_values(user, model, name, obj):
                refused[name] = str(
                    _('You may not set %(field)s to %(value)s.') % {'field': name, 'value': value}
                )

    return refused


def require_within_scope(user: User, action: str, obj: Model) -> None:
    """
    ``PermissionDenied`` unless ``obj``, as it is saved now, is among the rows
    ``user`` reaches for ``action``.

    Asked after the row is written and inside the transaction that wrote it,
    so the refusal undoes the write: a row made outside the scope ``create``
    was given in, or edited out of the scope ``edit`` was.
    """
    if not registry.policy_for(type(obj)).within_scope(user, action, obj):
        raise PermissionDenied


def write_action(view: object, *, creating: bool) -> str:
    """
    The action whose scope a row written by ``view`` must stay within:
    ``create`` for a new row; otherwise the view's own - ``approve`` for a view
    that approves - and ``edit`` for a view that names only how it reads.
    """
    if creating:
        return 'create'

    named = getattr(view, 'get_scope_action', None)
    action = named() if callable(named) else None
    return action if isinstance(action, str) and action not in _READS else 'edit'


def require_deletable(user: User, rows: Model | Iterable[Model]) -> None:
    """
    ``PermissionDenied`` unless deleting ``rows`` - a row, or several - takes
    only rows ``user`` may delete: those rows, and every row a cascade would
    take with them.

    Asked before the delete. A row deleted with another is deleted all the
    same, so somebody allowed to delete a loan but no payment would otherwise
    delete its payments. A cascade reaching a model the library guards - one
    with a ``ScopedQuerySet``, or permissions declared with
    ``build_permissions`` - asks its delete scope; another model's rows go as
    Django sends them, as its admin site does for a model it does not show.
    """
    found = [rows] if isinstance(rows, Model) else list(rows)

    if not found:
        return

    collector = _EveryRow(using=router.db_for_write(type(found[0])))
    collector.collect(found)

    for model, instances in collector.data.items():
        if not _guarded(model):
            continue

        keys = {instance.pk for instance in instances}
        reached = visible(model._default_manager.all(), user, 'delete').filter(pk__in=keys)

        if reached.count() != len(keys):
            raise PermissionDenied


class _EveryRow(Collector):
    """
    Django's collector, gathering every row a delete takes - as its admin site
    does - rather than deleting some by a query it never reads.
    """

    def can_fast_delete(self, *args: Any, **kwargs: Any) -> bool:
        return False


def _guarded(model: type[Model]) -> bool:
    """Whether the library guards ``model``'s rows: scoped, or declaring its permissions."""
    return isinstance(model._default_manager.all(), ScopedQuerySet) or isinstance(
        model._meta.permissions, DeclaredPermissions
    )
