"""The project's people in the admin site, with Django's own user admin."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from tests.project.accounts.models import Person

admin.site.register(Person, UserAdmin)
