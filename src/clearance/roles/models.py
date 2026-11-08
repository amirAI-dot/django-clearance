"""
Roles: what kind of person somebody is, kept in the database.

A role may start everybody holding it with bundles (``RoleBundle``), and may
set a ceiling (``RoleCeiling``) - the only permissions anybody holding it may
ever have, whatever bundle or grant gives them more. A role that is not
``limited`` has no ceiling. People are given roles here (``RoleAssignment``)
when the project reads them with ``AssignmentResolver``, the default.
"""

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.Model):
    code = models.CharField(_('code'), max_length=64, unique=True)
    name = models.CharField(_('name'), max_length=160)
    #: Whether a ceiling holds: when it does, those holding the role may have
    #: only what ``ceiling`` lists - nothing at all while it lists nothing.
    limited = models.BooleanField(_('limited'), default=True)

    class Meta:
        default_permissions = ()
        ordering = ('code',)
        verbose_name = _('role')
        verbose_name_plural = _('roles')

    def __str__(self) -> str:
        return self.name


class RoleAssignment(models.Model):
    """One person given one role."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='role_assignments'
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = (
            models.UniqueConstraint(fields=['user', 'role'], name='clearance_roles_once_each'),
        )

    def __str__(self) -> str:
        return f'{self.user}: {self.role}'


class RoleCeiling(models.Model):
    """One permission a limited role lets its holders have."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='ceiling')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='+')

    class Meta:
        default_permissions = ()
        constraints = (
            models.UniqueConstraint(
                fields=['role', 'permission'], name='clearance_roles_ceiling_once_each'
            ),
        )

    def __str__(self) -> str:
        return f'{self.role}: {self.permission}'


class RoleBundle(models.Model):
    """One bundle everybody holding a role starts with."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='bundles')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='role_bundles')

    class Meta:
        default_permissions = ()
        constraints = (
            models.UniqueConstraint(
                fields=['role', 'group'], name='clearance_roles_bundle_once_each'
            ),
        )

    def __str__(self) -> str:
        return f'{self.role}: {self.group}'
