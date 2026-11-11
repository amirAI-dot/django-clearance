"""
Roles, kept in the database: ``INSTALLED_APPS += ['clearance.roles']``, after
``'clearance'``.

Starting the app puts the roles' starting bundles and ceilings in force
(``clearance.limits``), so every permission check asks them inside the query
it already makes, and lets the ``ACCESS`` file declare roles. Without the app
installed, nothing about roles exists.
"""

from django.apps import AppConfig


class RolesConfig(AppConfig):
    name = 'clearance.roles'
    label = 'clearance_roles'
    default_auto_field = 'django.db.models.BigAutoField'

    # A product name, the same in every language - so not marked for translation.
    verbose_name = 'Clearance: roles'

    def ready(self) -> None:
        from django.core.checks import register

        from clearance.declared import register_section
        from clearance.limits import install
        from clearance.roles.checks import CHECKS
        from clearance.roles.declared import RoleSection
        from clearance.roles.limits import RoleLimits

        for check in CHECKS:
            register(check, 'clearance')

        install(RoleLimits())
        register_section(RoleSection())
