"""The lending app's pages, guarded the way a project on templates guards them."""

from django.http import HttpRequest, HttpResponse
from django.views.generic import DetailView, ListView, UpdateView

from clearance.decorators import policy_required
from clearance.views import PolicyRequiredMixin, ScopedQuerySetMixin
from tests.project.lending.models import Loan, Payment
from tests.project.lending.policies import loan_access


class LoanListView(PolicyRequiredMixin, ScopedQuerySetMixin, ListView):  # type: ignore[type-arg]
    policy = loan_access.policy
    queryset = Loan.objects.all()


class LoanDetailView(PolicyRequiredMixin, ScopedQuerySetMixin, DetailView):  # type: ignore[type-arg]
    policy = loan_access.policy
    queryset = Loan.objects.all()


class LoanApproveView(PolicyRequiredMixin, ScopedQuerySetMixin, UpdateView):  # type: ignore[type-arg]
    policy = loan_access.policy
    policy_action = 'approve'
    queryset = Loan.objects.all()
    fields = ('approved',)
    success_url = '/loans/'


class PaymentListView(PolicyRequiredMixin, ScopedQuerySetMixin, ListView):  # type: ignore[type-arg]
    """No policy named: the model's own is asked, with Django's own permissions."""

    queryset = Payment.objects.all()


@policy_required(loan_access.policy, 'create')
def apply(request: HttpRequest) -> HttpResponse:
    return HttpResponse('applied')
