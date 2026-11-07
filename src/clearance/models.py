"""
What the library adds to Django's own permission tables.

A bundle is Django's ``Group``, a person's bundles are ``user.groups``, and a
permission is an ``auth_permission`` row; none of that is copied here. These
tables hold only what Django has no place for: the scope a permission is
given with, and a permission taken away from one person.
"""

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from clearance.permissions import DEFAULT_ACTIONS, build_permissions


class Access(models.Model):
    """
    No table: the permissions to manage access itself.

    ``permission_view`` to look at who holds what; ``permission_create``,
    ``_edit`` and ``_delete`` to change it; ``role_ceiling_edit`` to widen
    what a role may ever hold. The superuser holds them all; nobody else does
    until given them.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            *build_permissions('permission', 'access', actions=DEFAULT_ACTIONS),
            ('role_ceiling_edit', 'Can change the ceilings of roles'),
        )
        verbose_name = _('access')
        verbose_name_plural = _('access')

    def __str__(self) -> str:
        return 'access'


class ScopeGrant(models.Model):
    """
    The scope a permission is given with - in a bundle, or to one person.

    A permission given with no row here reaches the model's
    ``default_scope``, and no rows when the model names none. Exactly one of
    ``group`` and ``user`` holds the grant.
    """

    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, null=True, blank=True, related_name='scope_grants'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='scope_grants',
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name='scope_grants'
    )
    scope = models.CharField(_('scope'), max_length=64)

    class Meta:
        default_permissions = ()
        verbose_name = _('scope grant')
        verbose_name_plural = _('scope grants')
        constraints = (
            models.CheckConstraint(
                condition=Q(group__isnull=False, user__isnull=True)
                | Q(group__isnull=True, user__isnull=False),
                name='clearance_scopegrant_one_holder',
            ),
            models.UniqueConstraint(
                fields=['group', 'permission'],
                condition=Q(group__isnull=False),
                name='clearance_scopegrant_one_per_group',
            ),
            models.UniqueConstraint(
                fields=['user', 'permission'],
                condition=Q(user__isnull=False),
                name='clearance_scopegrant_one_per_user',
            ),
        )

    def __str__(self) -> str:
        holder = self.group or self.user
        return f'{holder}: {self.permission.codename} in {self.scope}'


class PermissionRevocation(models.Model):
    """
    A permission taken away from one person, whatever bundle gives it.

    Django adds a person's own permissions to their groups' and has no way to
    take one away, so a bundle could be widened for one person but never
    narrowed. This row is the subtraction: ``ClearanceBackend`` leaves it out
    of what the person's bundles give.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='permission_revocations'
    )
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='+')
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    reason = models.TextField(_('reason'), blank=True)
    revoked_at = models.DateTimeField(_('revoked at'), auto_now_add=True)

    class Meta:
        default_permissions = ()
        verbose_name = _('revocation')
        verbose_name_plural = _('revocations')
        constraints = (
            models.UniqueConstraint(
                fields=['user', 'permission'], name='clearance_revocation_one_per_user'
            ),
        )

    def __str__(self) -> str:
        return f'{self.user}: {self.permission.codename} taken away'
