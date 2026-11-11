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
"""

from collections.abc import Mapping
from typing import Any

from django.db.models import Model
from django.utils.translation import gettext_lazy as _

from clearance.actions import clean_value, status_actions_of, writable_values
from clearance.fields import field_names, writable_fields
from clearance.protocols import User


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
