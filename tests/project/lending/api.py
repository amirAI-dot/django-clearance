"""
The lending app's API, guarded the way a project on DRF guards it.

A viewset of loans with an action of its own, a list of payments built from
DRF's generics, and a report that names the policy it asks.
"""

from typing import Any

from rest_framework import generics, serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from clearance.drf.permissions import ModelPolicyPermission, PolicyPermission
from clearance.drf.serializers import ProtectedFieldsSerializerMixin
from clearance.drf.viewsets import ScopedModelViewSet
from clearance.views import ScopedQuerySetMixin
from tests.project.lending.models import Loan, Payment
from tests.project.lending.policies import loan_access


class LoanSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Written knowing nothing of the library: the viewset protects it."""

    class Meta:
        model = Loan
        fields = ('id', 'applicant', 'amount', 'region', 'status', 'credit_score')
        read_only_fields = ('applicant',)


class LoanViewSet(ScopedModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    def perform_create(self, serializer: Any) -> None:
        serializer.save(applicant=self.request.user)

    @action(detail=True, methods=['post'])
    def remind(self, request: Request, pk: str | None = None) -> Response:
        """An action nobody wrote a hook for: lending.loan_remind, made on migrate."""
        return Response({'reminded': self.get_object().pk})


class PaymentSerializer(ProtectedFieldsSerializerMixin, serializers.ModelSerializer):  # type: ignore[type-arg]
    class Meta:
        model = Payment
        fields = ('id', 'loan', 'amount', 'state')


class PaymentList(ScopedQuerySetMixin, generics.ListCreateAPIView):  # type: ignore[type-arg]
    permission_classes = (ModelPolicyPermission,)
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class LoanReport(APIView):
    """No model of its own: it names the policy, and an action."""

    permission_classes = (PolicyPermission,)
    policy = loan_access.policy
    policy_action = 'report'

    def get(self, request: Request) -> Response:
        return Response({'loans': Loan.objects.visible_to(request.user).count()})
