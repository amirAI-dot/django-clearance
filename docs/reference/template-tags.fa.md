# تگ‌های قالب

## `{% load clearance %}`

### `label`

یک مجوز، یک بسته یا یک نقش را به زبان خواننده نام می‌برد:

```django
{% load clearance %}

{{ bundle|label }}            {# asks on its own #}
{{ bundle|label:labels }}     {# from the labels a page was given - no query #}
```

صفحه‌ای که چیزهای زیادی را نام می‌برد، اسم‌های زبانش را یک بار خوانده و می‌دهد:

```python
from clearance.labels import labels_in

context['labels'] = labels_in()    # every name of the active language, in one query
```

اسم از زبان خواننده خوانده می‌شود، بعد از زبان پایه‌ی آن، بعد از آنچه کد می‌گوید، و
بعد از خود ردیف.

## آنچه به یک قالب داده می‌شود

`ProtectedFieldsViewMixin` به قالب یک view در Django، `readable_fields` را می‌دهد،
فیلدهایی که شخص می‌تواند بخواند:

```django
{% if 'price' in readable_fields %}<td>{{ order.price }}</td>{% endif %}
```
