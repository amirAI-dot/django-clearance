# 9. Views and the API

The admin site asks the rules with no code. Django's views and DRF ask them
through a few classes, and the serializer, the form and the template know
nothing of access.

## Django's views

```python
--8<-- "example/shop/views.py"
```

* `ScopedQuerySetMixin` narrows the queryset to the rows the person reaches.
* `PolicyRequiredMixin` asks the policy. The action is read off the view -
  `ListView` is `list`, `UpdateView` is `edit` - or named with
  `policy_action`.
* `ProtectedFieldsViewMixin` builds the form for the person, and gives the
  template `readable_fields`:

```django
{% if 'price' in readable_fields %}<td>{{ order.price }}</td>{% endif %}
```

## The API

```python
--8<-- "example/shop/api.py"
```

`ScopedModelViewSet` narrows the rows, asks the model's policy for each
action, and leaves out the fields the person may not read. A write naming a
field they may not write - or a status value they may not set - is a 400
naming the field.

`print_invoice` is an action found in the code: `migrate` makes its
permission, `shop.order_print_invoice`, and only whoever holds it may call it.

## A view that holds no record

With `ModelPolicyPermission` as the default, a view with no model and no
policy is refused at start-up (E009) - DRF's own router root among them. The
shop gives it the permission it needs:

```python
--8<-- "example/shop/urls.py"
```

## Try it

Signed in as `alice`, post to `/api/orders/`:

```json
{"branch": 1, "item": "Clock", "price": "1.00"}
```

The answer is a 400 naming `price`: a customer may place an order, and never
price it.
