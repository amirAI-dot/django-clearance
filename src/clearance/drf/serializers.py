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
from django.db.models import Model
from rest_framework import serializers

from clearance.fields import protection_of, readable_fields, writable_fields
from clearance.protocols import User
from clearance.writes import refused_writes


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
            return fields

        readable, writable = readable_fields(user, model), writable_fields(user, model)

        for name, field in list(fields.items()):
            target = field.source or name

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

        return super().to_internal_value(data)  # type: ignore[misc]


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
