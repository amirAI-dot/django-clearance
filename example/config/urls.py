"""The shop's addresses: the admin site, the order pages and the API."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
]
