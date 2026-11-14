"""
Django's admin, with the library's site as the default one.

Named in ``INSTALLED_APPS`` in place of ``'django.contrib.admin'``. Django's
own page for groups is taken away: a bundle is a group, and that page wrote
round every safety rule - the bundle pages write through ``AccessService``.
"""

from django.contrib.admin.apps import AdminConfig


class ClearanceAdminConfig(AdminConfig):
    """Django's admin app, with ``ClearanceAdminSite`` as its default site."""

    default_site = 'clearance.admin.sites.ClearanceAdminSite'

    def ready(self) -> None:
        super().ready()

        from django.contrib import admin
        from django.contrib.auth.models import Group

        if admin.site.is_registered(Group):
            admin.site.unregister(Group)
