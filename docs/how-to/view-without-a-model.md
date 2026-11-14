# A view that holds no model

With `ModelPolicyPermission` as DRF's default, every view asks the policy of
its model - and a view with no model, and no policy named, is refused at
start-up (E009). So a view of no model says what it asks.

## A report, on a model's policy

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

`report` is an action found in the code: `migrate` makes
`shop.order_report`, held by nobody until it is given. The rows are still the
person's - `visible_to` narrows them.

## A function view

```python
from clearance.decorators import policy_required


@policy_required(order_access.policy, 'export')
def export(request):
    ...
```

## A view that holds no record at all

DRF's router root lists the endpoints and holds nothing. Give it the
permission it needs:

```python
from rest_framework import routers
from rest_framework.permissions import IsAuthenticated


class ShopRouter(routers.DefaultRouter):
    class APIRootView(routers.APIRootView):
        permission_classes = (IsAuthenticated,)
```

A health check, a login view, a webhook: the same - name their own
`permission_classes`.
