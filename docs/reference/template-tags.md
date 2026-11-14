# Template tags

## `{% load clearance %}`

### `label`

Names a permission, a bundle or a role in the reader's language:

```django
{% load clearance %}

{{ bundle|label }}            {# asks on its own #}
{{ bundle|label:labels }}     {# from the labels a page was given - no query #}
```

A page that names many things passes the names of its language, read once:

```python
from clearance.labels import labels_in

context['labels'] = labels_in()    # every name of the active language, in one query
```

A name reads from the reader's language, then its base language, then what
the code says, then the row.

## What a template is given

`ProtectedFieldsViewMixin` gives a Django view's template `readable_fields`,
the fields the person may read:

```django
{% if 'price' in readable_fields %}<td>{{ order.price }}</td>{% endif %}
```
