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
  protected fields, whether or not it was written to; and DRF's
  ``SearchFilter`` and ``OrderingFilter`` - and django-filter's
  ``DjangoFilterBackend``, when it is installed - leave out a field the person
  may not read: searching, sorting or filtering by it tells what it holds. A
  filter of the project's own asks ``clearance.fields.path_readable`` for itself.
"""

from functools import cache
from typing import Any

from rest_framework import filters, viewsets

from clearance.drf.permissions import ModelPolicyPermission
from clearance.drf.serializers import protected_serializer
from clearance.fields import path_readable
from clearance.protocols import user_of
from clearance.views import ScopedQuerySetMixin


class ProtectedSerializerMixin:
    """Gives a DRF view's serializer ``ProtectedFieldsSerializerMixin``, made once per class."""

    def get_serializer_class(self) -> type[Any]:
        return protected_serializer(super().get_serializer_class())  # type: ignore[misc]

    def filter_queryset(self, queryset: Any) -> Any:
        """DRF's own, with each backend searching and sorting by readable fields only."""
        for backend in list(self.filter_backends):  # type: ignore[attr-defined]
            queryset = protected_backend(backend)().filter_queryset(self.request, queryset, self)  # type: ignore[attr-defined]

        return queryset


class ReadableSearchMixin:
    """A ``SearchFilter`` that searches only the fields the person may read."""

    def get_search_fields(self, view: Any, request: Any) -> Any:
        fields = super().get_search_fields(view, request)  # type: ignore[misc]
        model = getattr(getattr(view, 'queryset', None), 'model', None) or view.get_queryset().model
        user = user_of(request)
        return [field for field in fields or () if path_readable(user, model, str(field))]


class ReadableOrderingMixin:
    """An ``OrderingFilter`` that sorts only by the fields the person may read."""

    def get_ordering(self, request: Any, queryset: Any, view: Any) -> Any:
        ordering = super().get_ordering(request, queryset, view)  # type: ignore[misc]
        user = user_of(request)
        return [
            field
            for field in ordering or ()
            if not isinstance(field, str) or path_readable(user, queryset.model, field)
        ]


class ReadableFilterSetMixin:
    """A ``DjangoFilterBackend`` whose filtersets filter only by the fields the person may read."""

    def get_filterset(self, request: Any, queryset: Any, view: Any) -> Any:
        filterset = super().get_filterset(request, queryset, view)  # type: ignore[misc]

        if filterset is not None:
            user = user_of(request)

            for name, found in list(filterset.filters.items()):
                if not path_readable(user, queryset.model, found.field_name):
                    del filterset.filters[name]  # as if the filterset never had it

        return filterset


def _backends() -> list[tuple[type[Any], type[Any]]]:
    """Each filter backend the library knows, with what it adds - django-filter's if installed."""
    known: list[tuple[type[Any], type[Any]]] = [
        (ReadableSearchMixin, filters.SearchFilter),
        (ReadableOrderingMixin, filters.OrderingFilter),
    ]

    try:
        from django_filters.rest_framework import DjangoFilterBackend
    except ImportError:  # the project does not use it
        return known

    return [*known, (ReadableFilterSetMixin, DjangoFilterBackend)]


@cache
def protected_backend(backend: type[Any]) -> type[Any]:
    """``backend``, leaving out what the person may not read - made once per class."""
    mixins = [
        mixin
        for mixin, base in _backends()
        if issubclass(backend, base) and not issubclass(backend, mixin)
    ]
    return type(backend.__name__, (*mixins, backend), {}) if mixins else backend


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
