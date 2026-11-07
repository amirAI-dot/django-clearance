"""The lending app's pages."""

from django.urls import path

from tests.project.lending import views

urlpatterns = [
    path('', views.LoanListView.as_view(), name='loan-list'),
    path('<int:pk>/', views.LoanDetailView.as_view(), name='loan-detail'),
    path('<int:pk>/approve/', views.LoanApproveView.as_view(), name='loan-approve'),
    path('apply/', views.apply, name='loan-apply'),
    path('payments/', views.PaymentListView.as_view(), name='payment-list'),
]
