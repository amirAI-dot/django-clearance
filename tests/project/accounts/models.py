"""
The test project's people: a user model of the project's own.

The library never needs a particular user model; this one is the project's,
as most are, so the suite proves the library works with it.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class Person(AbstractUser):
    #: Where the person works or lives - something of theirs a rule can compare with.
    region = models.CharField(max_length=32, blank=True)
    #: The largest loan the person may decide on - a number of theirs a rule can compare with.
    approval_limit = models.PositiveIntegerField(default=0)
