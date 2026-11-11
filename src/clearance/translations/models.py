"""
A name, and what it is for, in one language - of a permission, a bundle, or
a role.

One table for all three, keyed by what is named: a table per kind would tie
this app to every app whose things it names, and a project without roles
would not start. A name goes when the thing it names is deleted.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class Translation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='+')
    object_pk = models.CharField(_('object'), max_length=64)
    language = models.CharField(_('language'), max_length=16)
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)

    class Meta:
        default_permissions = ()
        verbose_name = _('name in a language')
        verbose_name_plural = _('names in languages')
        constraints = (
            models.UniqueConstraint(
                fields=['content_type', 'object_pk', 'language'],
                name='clearance_translations_once_each',
            ),
        )

    def __str__(self) -> str:
        return f'{self.language}: {self.name}'
