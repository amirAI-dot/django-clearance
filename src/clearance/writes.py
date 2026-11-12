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

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.utils.translation import gettext_lazy as _

from clearance.actions import clean_value, status_actions_of, writable_values
from clearance.fields import field_names, writable_fields
from clearance.protocols import User
from clearance.registry import registry

#: The actions that only look: a write made by a view of one is an edit.
_READS = frozenset({'view', 'list'})


def refused_writes(
    user: User, model: type[Model], data: Mapping[str, Any], obj: Model | None = None
) -> dict[str, str]:
    """``{field: why}`` for every value in ``data`` ``user`` may not write to ``obj``."""
    names = set(field_names(model))
    sent = {name: value for name, value in data.items() if name in names}

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
