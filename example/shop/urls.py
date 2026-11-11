from django.urls import include, path
from rest_framework import routers
from rest_framework.permissions import IsAuthenticated

from shop import api, views


class ShopRouter(routers.DefaultRouter):
    class APIRootView(routers.APIRootView):
        """
        The list of endpoints holds no record, so it asks no policy - said here,
        because every view asks one unless it says otherwise (E009).
        """

        permission_classes = (IsAuthenticated,)


router = ShopRouter()
router.register('orders', api.OrderViewSet)

urlpatterns = [
    path('orders/', views.OrderList.as_view(), name='orders'),
    path('orders/<int:pk>/', views.OrderEdit.as_view(), name='order'),
    path('api/', include(router.urls)),
]
