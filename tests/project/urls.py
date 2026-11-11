"""The test project's URLs: each app's pages under a prefix, as projects mount them."""

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tests.project.lending import api

router = DefaultRouter()
router.register('loans', api.LoanViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('loans/', include('tests.project.lending.urls')),
    path('api/', include(router.urls)),
    path('api/payments/', api.PaymentList.as_view()),
    path('api/report/', api.LoanReport.as_view()),
]
