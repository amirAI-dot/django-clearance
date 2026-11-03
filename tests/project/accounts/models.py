"""
The test project's people: Django's user, with roles.

``role`` is the single column most projects already have, which the default
resolver reads. ``extra_roles`` lets a test give somebody several - codes
separated by commas, in a plain column any database stores - read through
``roles`` with ``ROLE_ATTRIBUTE`` set to it.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class Person(AbstractUser):
    role = models.CharField(max_length=32, blank=True)
    extra_roles = models.CharField(max_length=200, blank=True)

    @property
    def roles(self) -> list[str]:
        return [code for code in (self.role, *self.extra_roles.split(',')) if code]
