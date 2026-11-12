"""
A serializer that shows a person only the fields they may read, and takes
only the values they may write::

    class LoanSerializer(ProtectedFieldsSerializerMixin, serializers.ModelSerializer):
        class Meta:
            model = Loan
            fields = ('id', 'amount', 'rate', 'status')

A protected field the person may not read is **left out** - the key is not in
the answer. One they may read but not write is **read only**. A value sent
for either, or a value a status action claims that they are not allowed, is
**refused**, naming the field - never silently dropped, so a client that
thinks it saved something is told it did not.

**A related row's fields are protected the same.** A serializer nested in this
one - written out, or made by ``depth`` - is given this mixin too, so a
payment does not show the credit score of its loan. And a value is refused
under whatever name the serializer gives its field: ``decision``, with
``source='status'``, is the status.

**What it saves stays among the rows the person reaches**: a row made outside
the scope ``create`` was given in, or edited out of the scope it was reached
in, is refused with a 403 and the write undone - whatever ``perform_create``
the view wrote, because it is ``save`` that asks.

The person is the request's (``context['request'].user``), or
``context['user']`` for a serializer used outside a view. A serializer with
neither refuses to be built: one that forgot whose it is would show every
field to everybody.

``ScopedModelViewSet`` and ``ProtectedSerializerMixin`` put this on a view's
serializer themselves.
"""

from collections.abc import Mapping
from functools import cache
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Model
from rest_framework import serializers

from clearance.fields import protection_of, readable_fields, writable_fields
from clearance.protocols import User
from clearance.writes import refused_writes, require_within_scope, write_action


class ProtectedFieldsSerializerMixin:
    """Leaves out, locks and refuses what the person may not read or write."""

    context: Mapping[str, Any]
    instance: Any

    @property
    def protected_for(self) -> User:
        """Whose serializer this is: the request's person, or ``context['user']``."""
        user = self.context.get('user') or getattr(self.context.get('request'), 'user', None)

        if user is None:
            raise ImproperlyConfigured(
                f'{type(self).__name__} cannot tell whose fields to show: give it the request, '
                f"or context={{'user': ...}}."
            )

        return user  # type: ignore[no-any-return]

    @property
    def protected_model(self) -> type[Model]:
        model = getattr(getattr(self, 'Meta', None), 'model', None)

        if model is None:
            raise ImproperlyConfigured(
                f'{type(self).__name__} protects the fields of a model: use it on a '
                f'ModelSerializer.'
            )

        return model  # type: ignore[no-any-return]

    def get_fields(self) -> dict[str, serializers.Field]:  # type: ignore[type-arg]
        fields: dict[str, serializers.Field] = super().get_fields()  # type: ignore[misc, type-arg]
        model, user = self.protected_model, self.protected_for
        protected = protection_of(user).fields(model)

        if not protected:
            for field in fields.values():
                _protect_nested(field)
            return fields

        readable, writable = readable_fields(user, model), writable_fields(user, model)

        for name, field in list(fields.items()):
            target = field.source or name

            _protect_nested(field)

            if target not in protected:
                continue

            if target not in readable:
                del fields[name]
            elif target not in writable:
                field.read_only, field.required = True, False

        return fields

    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, Mapping):
            obj = self.instance if isinstance(self.instance, Model) else None
            refused = refused_writes(self.protected_for, self.protected_model, data, obj)

            if refused:
                raise serializers.ValidationError({name: [why] for name, why in refused.items()})

        validated = super().to_internal_value(data)  # type: ignore[misc]

        if isinstance(validated, Mapping):
            # Again by the names of the model's fields: a field may be sent under another.
            self._refuse(validated)

        return validated

    def build_nested_field(self, *args: Any, **kwargs: Any) -> Any:
        """A serializer ``depth`` makes for a related row protects that row's fields too."""
        field_class, field_kwargs = super().build_nested_field(*args, **kwargs)  # type: ignore[misc]
        return protected_serializer(field_class), field_kwargs

    def _refuse(self, validated: Mapping[str, Any]) -> None:
        obj = self.instance if isinstance(self.instance, Model) else None
        refused = refused_writes(self.protected_for, self.protected_model, validated, obj)

        if refused:
            named = {field.source: name for name, field in self.fields.items()}  # type: ignore[attr-defined]
            raise serializers.ValidationError(
                {named.get(source, source): [why] for source, why in refused.items()}
            )

    def save(self, **kwargs: Any) -> Any:
        creating = self.instance is None

        with transaction.atomic():
            saved = super().save(**kwargs)  # type: ignore[misc]

            if isinstance(saved, Model):
                action = write_action(self.context.get('view'), creating=creating)
                require_within_scope(self.protected_for, action, saved)

        return saved


def _protect_nested(field: Any) -> None:
    """
    Give a serializer nested in a protected one the mixin too - in place: it
    is already built, and reads whose it is from the serializer it is in.
    """
    nested = field.child if isinstance(field, serializers.ListSerializer) else field

    if isinstance(nested, serializers.ModelSerializer) and not isinstance(
        nested, ProtectedFieldsSerializerMixin
    ):
        nested.__class__ = protected_serializer(type(nested))


@cache
def protected_serializer(serializer_class: type[Any]) -> type[Any]:
    """
    ``serializer_class`` with ``ProtectedFieldsSerializerMixin`` - made once
    per class. A serializer of no model is returned as it is: its writes are
    the permission class's to guard.
    """
    if issubclass(serializer_class, ProtectedFieldsSerializerMixin) or not issubclass(
        serializer_class, serializers.ModelSerializer
    ):
        return serializer_class

    metaclass: Any = type(serializer_class)
    protected: type[Any] = metaclass(
        serializer_class.__name__,
        (ProtectedFieldsSerializerMixin, serializer_class),
        {'__module__': serializer_class.__module__},
    )
    return protected
