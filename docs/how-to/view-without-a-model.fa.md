# viewای که مدل ندارد

وقتی `ModelPolicyPermission` پیش‌فرض DRF باشد، هر view از policy مدل خودش می‌پرسد - و
viewای که نه مدل دارد و نه policyای نام می‌برد، موقع بالا آمدن پروژه رد می‌شود
(E009). پس viewای بدون مدل می‌گوید از چه چیزی می‌پرسد.

## یک گزارش، روی policy یک مدل

```python
from rest_framework.views import APIView

from clearance.drf.permissions import PolicyPermission
from shop.policies import order_access


class OrderReport(APIView):
    permission_classes = (PolicyPermission,)
    policy = order_access.policy
    policy_action = 'report'

    def get(self, request):
        orders = Order.objects.visible_to(request.user)
        ...
```

`report` اکشنی است که در کد پیدا می‌شود: `migrate` مجوز `shop.order_report` را
می‌سازد، که تا داده نشود هیچ کس آن را ندارد. ردیف‌ها هنوز مال خود شخص‌اند -
`visible_to` محدودشان می‌کند.

## یک view تابعی

```python
from clearance.decorators import policy_required


@policy_required(order_access.policy, 'export')
def export(request):
    ...
```

## viewای که اصلاً رکوردی ندارد

صفحه‌ی اصلی router در DRF endpointها را فهرست می‌کند و چیزی را نگه نمی‌دارد. مجوزی
را که لازم دارد به آن بدهید:

```python
from rest_framework import routers
from rest_framework.permissions import IsAuthenticated


class ShopRouter(routers.DefaultRouter):
    class APIRootView(routers.APIRootView):
        permission_classes = (IsAuthenticated,)
```

بررسی سلامت سرویس، view ورود، یک webhook: همین‌طور - `permission_classes` خودشان را
نام ببرند.
