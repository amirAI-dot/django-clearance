"""
The lending app in the admin site, written exactly as Django documents it:
nothing here knows about the library, and the library's site guards it all.
"""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from tests.project.lending.models import Loan, Payment


class PaymentInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Payment
    extra = 0


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ('id', 'applicant', 'amount', 'region', 'status', 'credit_score')
    list_editable = ('region', 'credit_score')
    list_filter = ('status', 'credit_score')
    search_fields = ('region', 'credit_score', 'applicant__username')
    ordering = ('-credit_score', 'id')
    fieldsets = ((None, {'fields': ('applicant', ('amount', 'credit_score'), 'region', 'status')}),)
    inlines = (PaymentInline,)
    actions = ('mark_reviewed', 'archive')

    @admin.action(description='Mark as reviewed')
    def mark_reviewed(self, request: HttpRequest, queryset: QuerySet[Loan]) -> None:
        """Nobody wrote a permission for it: lending.loan_mark_reviewed, made on migrate."""
        queryset.update(region='reviewed')

    @admin.action(description='Archive', permissions=('change',))
    def archive(self, request: HttpRequest, queryset: QuerySet[Loan]) -> None:
        """Django's own permission decides it: no permission is made for it."""
        queryset.update(region='archived')


admin.site.register(Payment)
