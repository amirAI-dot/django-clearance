"""
The viewsets most projects write, guarded and scoped::

    class OrderViewSet(ScopedModelViewSet):
        queryset = Order.objects.all()
        serializer_class = OrderSerializer

Each is DRF's own viewset with three things added, every one of which also
works on its own on any other DRF view:

* ``ScopedQuerySetMixin`` - the rows the person reaches for the action;
* ``ModelPolicyPermission`` - the model's policy asked, writes guarded;
* ``ProtectedSerializerMixin`` - the serializer leaves out and locks the
  protected fields, whether or not it was written to.
"""

from typing import Any

from rest_framework import viewsets

from clearance.drf.permissions import ModelPolicyPermission
from clearance.drf.serializers import protected_serializer
from clearance.views import ScopedQuerySetMixin


class ProtectedSerializerMixin:
    """Gives a DRF view's serializer ``ProtectedFieldsSerializerMixin``, made once per class."""

    def get_serializer_class(self) -> type[Any]:
        return protected_serializer(super().get_serializer_class())  # type: ignore[misc]


class ScopedModelViewSet(  # type: ignore[misc]
    ProtectedSerializerMixin,
    ScopedQuerySetMixin,
    viewsets.ModelViewSet,  # type: ignore[type-arg]
):
    """A ``ModelViewSet`` asking the model's policy, over the rows the person reaches."""

    permission_classes: Any = (ModelPolicyPermission,)


class ScopedReadOnlyViewSet(  # type: ignore[misc]
    ProtectedSerializerMixin,
    ScopedQuerySetMixin,
    viewsets.ReadOnlyModelViewSet,  # type: ignore[type-arg]
):
    """A ``ReadOnlyModelViewSet`` asking the model's policy, over the rows the person reaches."""

    permission_classes: Any = (ModelPolicyPermission,)
