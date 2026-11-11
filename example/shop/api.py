"""
The orders API. The serializer knows nothing of access: the viewset narrows
the rows, asks the policy, and leaves out the price for whoever may not read it.
"""

from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from clearance.drf.viewsets import ScopedModelViewSet
from shop.models import Order


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('id', 'customer', 'branch', 'item', 'status', 'price')
        read_only_fields = ('customer',)


class OrderViewSet(ScopedModelViewSet):
    queryset = Order.objects.select_related('branch')
    serializer_class = OrderSerializer

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

    @action(detail=True, methods=['post'])
    def print_invoice(self, request, pk=None):
        """Found in the code: shop.order_print_invoice is made by migrate."""
        order = self.get_object()
        return Response({'invoice': f'INV-{order.pk:05d}', 'item': order.item})
