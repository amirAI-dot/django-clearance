"""The test project's URLs: each app's pages under a prefix, as projects mount them."""

from django.urls import include, path

urlpatterns = [
    path('loans/', include('tests.project.lending.urls')),
]
