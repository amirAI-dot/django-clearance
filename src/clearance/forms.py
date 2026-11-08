"""
A Django form that shows a person only the fields they may see.

    class LoanForm(ProtectedFieldsFormMixin, forms.ModelForm):
        class Meta:
            model = Loan
            fields = ('amount', 'rate')

    form = LoanForm(request.POST or None, instance=loan, user=request.user)

A protected field the person may not read is **left out** of the form; one
they may read but not write is shown **disabled**, so Django keeps the
value the row already holds whatever the browser sends. Fields nobody
protected are left as the form declared them.

``user`` is required: a form that forgot whose it is would show every field
to everybody, so it refuses to be built instead.
"""

from typing import Any

from django import forms
from django.core.exceptions import ImproperlyConfigured

from clearance.fields import protection_of, readable_fields, writable_fields
from clearance.protocols import User


class ProtectedFieldsFormMixin:
    """Leaves out what ``user`` may not read, and disables what they may not write."""

    fields: dict[str, forms.Field]

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
