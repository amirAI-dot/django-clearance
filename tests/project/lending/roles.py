"""Roles as a choices class, the shape most projects declare them in."""

from django.db import models


class Role(models.TextChoices):
    ADMIN = 'admin', 'Administrator'
    OFFICER = 'officer', 'Loan officer'
