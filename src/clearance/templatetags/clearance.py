"""
``{% load clearance %}`` - ``{{ permission|label:labels }}`` names a permission,
a bundle or a role in the reader's language, from the ``labels`` a page was
given; without them, it asks on its own.
"""

from typing import Any

from django import template

from clearance.labels import Labels, label_of

register = template.Library()


@register.filter
def label(thing: Any, labels: Labels | None = None) -> str:
    return labels.of(thing) if isinstance(labels, Labels) else label_of(thing)
