"""
A Django form that shows a person only the fields - and the values - they may.

    class LoanForm(ProtectedFieldsFormMixin, forms.ModelForm):
        class Meta:
            model = Loan
            fields = ('amount', 'rate', 'status')

    form = LoanForm(request.POST or None, instance=loan, user=request.user)

A protected field the person may not read is **left out** of the form; one
they may read but not write is shown **disabled**, so Django keeps the
value the row already holds whatever the browser sends. A field a status
action writes **offers only the values they may write** - ``approved`` only
to whoever may approve - and a value sent past that is refused, naming the
field. Everything else is left as the form declared it.

``user`` is required: a form that forgot whose it is would show every field
to everybody, so it refuses to be built instead.
"""

from collections.abc import Iterable
from typing import Any

from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.translation import gettext_lazy as _

from clearance.actions import status_actions_of, writable_values
from clearance.fields import protection_of, readable_fields, writable_fields
from clearance.protocols import User


class ProtectedFieldsFormMixin:
    """Leaves out, disables and narrows what ``user`` may not read, write, or set."""

    fields: dict[str, forms.Field]
    instance: Any

    def __init__(self, *args: Any, user: User, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        model = getattr(getattr(self, '_meta', None), 'model', None)

        if model is None:
            raise ImproperlyConfigured(
                f'{type(self).__name__} protects the fields of a model: use it on a ModelForm.'
            )

        self.protected_for = user
        protected = protection_of(user).fields(model)
        readable, writable = readable_fields(user, model), writable_fields(user, model)

        for name in [name for name in self.fields if name in protected]:
            if name not in readable:
                del self.fields[name]
            elif name not in writable:
                self.fields[name].disabled = True

        #: The values each field a status action writes may be set to, by this person.
        self.writable_values: dict[str, frozenset[Any]] = {
            name: writable_values(user, model, name, self.instance)
            for name in status_actions_of(user).fields(model)
            if name in self.fields and not self.fields[name].disabled
        }

        for name, allowed in self.writable_values.items():
            field: Any = self.fields[name]

            if hasattr(field, 'choices'):
                field.choices = list(_offered(field.choices, allowed))

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean()  # type: ignore[misc]

        for name, allowed in self.writable_values.items():
            if name in cleaned and cleaned[name] not in allowed:
                self.add_error(  # type: ignore[attr-defined]
                    name,
                    ValidationError(
                        _('You may not set %(field)s to %(value)s.'),
                        code='value_not_allowed',
                        params={'field': name, 'value': cleaned[name]},
                    ),
                )

        return cleaned


def _offered(choices: Iterable[Any], allowed: frozenset[Any]) -> Iterable[Any]:
    """``choices`` without the values not ``allowed`` - the empty choice kept, groups too."""
    for value, label in choices:
        if isinstance(label, list | tuple):
            inner = list(_offered(label, allowed))
            if inner:
                yield value, inner
        elif value in ('', None) or value in allowed:
            yield value, label
