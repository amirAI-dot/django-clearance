"""
The test project's people: a user model of the project's own.

The library never needs a particular user model; this one is the project's,
as most are, so the suite proves the library works with it.
"""

from django.contrib.auth.models import AbstractUser


class Person(AbstractUser):
    pass
