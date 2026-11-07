"""
DRF's views, checked at start-up - registered when ``rest_framework`` is installed.

==================  =========================================================
``clearance.E003``  a view asking a model's policy serializes the model
                    without leaving out its protected fields
``clearance.E009``  a view guarded by a policy has no policy to ask
==================  =========================================================

E003 holds for every model, not only one protecting fields today: a field an
administrator protects tomorrow, in the admin site, would otherwise be shown
to everybody by a serializer nobody changed.
"""

from collections.abc import Iterable
from typing import Any

from django.core.checks import CheckMessage, Error
from rest_framework import serializers
from rest_framework.views import APIView

from clearance.drf.discovery import guarded_views, guarding_policy
from clearance.drf.permissions import ModelPolicyPermission, finds_model_by_queryset
from clearance.drf.serializers import ProtectedFieldsSerializerMixin
from clearance.drf.viewsets import ProtectedSerializerMixin


def api_view_errors(views: Iterable[type[APIView]]) -> list[CheckMessage]:
    """E009 and E003, for each of ``views``."""
    errors: list[CheckMessage] = []

    for view in views:
        if guarding_policy(view) is None and not _finds_model_later(view):
            errors.append(
                Error(
                    f'{view.__name__} asks a policy, but names none and has no queryset to '
                    f'find its model by.',
                    hint='Set policy = ..., or queryset = Model.objects.all().',
                    obj=view,
                    id='clearance.E009',
                )
            )

        unprotected = _unprotected_serializer(view)

        if unprotected is not None:
            errors.append(
                Error(
                    f'{view.__name__} serializes its model with {unprotected.__name__}, which '
                    f'would show a protected field to everybody.',
                    hint='Add ProtectedFieldsSerializerMixin to the serializer, or '
                    'ProtectedSerializerMixin to the view.',
                    obj=view,
                    id='clearance.E003',
                )
            )

    return errors


def check_api_views(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    try:
        views = list(dict.fromkeys(view for view, _ in guarded_views()))
    except Exception:
        # A URLconf that does not import is Django's own check to report.
        return []

    return api_view_errors(views)


def _finds_model_later(view: type[APIView]) -> bool:
    """A model-policy view whose own ``get_queryset`` finds its model when asked."""
    asks_the_model = any(
        isinstance(permission, type) and issubclass(permission, ModelPolicyPermission)
        for permission in view.permission_classes
    )
    return asks_the_model and finds_model_by_queryset(view)


def _unprotected_serializer(view: type[APIView]) -> type | None:
    """The model serializer ``view`` names that would show every field, if it names one."""
    serializer = getattr(view, 'serializer_class', None)
    unprotected = (
        isinstance(serializer, type)
        and issubclass(serializer, serializers.ModelSerializer)
        and not issubclass(serializer, ProtectedFieldsSerializerMixin)
        and not issubclass(view, ProtectedSerializerMixin)
    )
    return serializer if unprotected else None


#: Every DRF check, registered by the app when DRF is installed.
CHECKS = (check_api_views,)
