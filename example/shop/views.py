"""The order pages, for a project on templates: the same rules as the API."""

from django.views.generic import ListView, UpdateView

from clearance.views import PolicyRequiredMixin, ProtectedFieldsViewMixin, ScopedQuerySetMixin
from shop.models import Order
from shop.policies import order_access


class OrderList(ProtectedFieldsViewMixin, PolicyRequiredMixin, ScopedQuerySetMixin, ListView):
    """Only the orders the person may view; the price only when they may read it."""

    policy = order_access.policy
    queryset = Order.objects.select_related('branch', 'customer')
    template_name = 'shop/orders.html'


class OrderEdit(ProtectedFieldsViewMixin, PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):
    """The form offers only the fields, and the status values, the person may write."""

    policy = order_access.policy
    queryset = Order.objects.all()
    fields = ('item', 'status', 'price')
    template_name = 'shop/order_form.html'
    success_url = '/orders/'
