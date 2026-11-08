"""
What the library adds to Django's own permission tables.

A bundle is Django's ``Group``, a person's bundles are ``user.groups``, and a
permission is an ``auth_permission`` row; none of that is copied here. These
tables hold only what Django has no place for: the scope a permission is
given with, a permission taken away from one person, the scopes an
administrator builds from rules, the fields they protect, the status
actions they make - and which of all that the ``ACCESS`` file owns.
"""

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from clearance.permissions import DEFAULT_ACTIONS, build_permissions

if TYPE_CHECKING:
    from clearance.fields import Protection
    from clearance.rules import Rule


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


class ScopeRule(models.Model):
    """
    A row scope an administrator built, from rules - offered beside the code's.

    ``conditions`` is a list of ``{'field': ..., 'operator': ..., 'value': ...}``,
    joined by ``match``: ``all`` of them, or ``any``. It is checked against the
    model whenever it is saved (``clearance.rules``), and turned into a ``Q``
    when a list is asked for.
    """

    MATCH_CHOICES = (('all', _('all of the conditions')), ('any', _('any of the conditions')))

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+', verbose_name=_('model')
    )
    code = models.CharField(_('code'), max_length=64)
    name = models.CharField(_('name'), max_length=160)
    match = models.CharField(_('match'), max_length=3, choices=MATCH_CHOICES, default='all')
    conditions = models.JSONField(_('conditions'), default=list)

    class Meta:
        default_permissions = ()
        verbose_name = _('scope rule')
        verbose_name_plural = _('scope rules')
        constraints = (
            models.UniqueConstraint(
                fields=['content_type', 'code'], name='clearance_scoperule_one_code_per_model'
            ),
        )

    def __str__(self) -> str:
        return f'{self.content_type.model}: {self.name}'

    def compiled(self, protection: 'Protection | None' = None) -> 'Rule':
        """The rule, checked against its model - and what is protected - as they are now."""
        from clearance.rules import Rule

        model = self.content_type.model_class()

        if model is None:
            from django.core.exceptions import ValidationError

            raise ValidationError('The model of this rule no longer exists.')

        return Rule.parse(model, self.match, self.conditions, protection=protection)


class ProtectedField(models.Model):
    """
    A field an administrator protected: read with one permission, written
    with another, both made when it was protected and deleted with it.

    A field protected in code (``build_permissions(protected_fields=...)``) has
    no row here; ``clearance.fields`` reads both.
    """

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+', verbose_name=_('model')
    )
    field = models.CharField(_('field'), max_length=64)

    class Meta:
        default_permissions = ()
        verbose_name = _('protected field')
        verbose_name_plural = _('protected fields')
        constraints = (
            models.UniqueConstraint(
                fields=['content_type', 'field'], name='clearance_protectedfield_once_per_model'
            ),
        )

    def __str__(self) -> str:
        return f'{self.content_type.model}.{self.field}'


class StatusAction(models.Model):
    """
    An action an administrator made that writes values: ``approve`` sets
    ``status`` to ``approved`` or ``rejected``, from ``pending``.

    Its permission - ``<codename>_<code>`` - is made with it and deleted with
    it. A status action declared in code (``build_permissions(status_actions=
    ...)``) has no row here; ``clearance.actions`` reads both.
    """

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+', verbose_name=_('model')
    )
    code = models.CharField(_('code'), max_length=64)
    name = models.CharField(_('name'), max_length=160)
    field = models.CharField(_('field'), max_length=64)
    #: The values only this action writes.
    to_values = models.JSONField(_('to'), default=list)
    #: The values it may write them from; empty is from any value.
    from_values = models.JSONField(_('from'), default=list, blank=True)

    class Meta:
        default_permissions = ()
        verbose_name = _('status action')
        verbose_name_plural = _('status actions')
        constraints = (
            models.UniqueConstraint(
                fields=['content_type', 'code'], name='clearance_statusaction_one_code_per_model'
            ),
        )

    def __str__(self) -> str:
        return f'{self.content_type.model}: {self.name}'


class Declared(models.Model):
    """
    Something the ``ACCESS`` file owns - a bundle, a role, a status action.

    ``clearance_sync`` makes, changes and deletes what is listed here, and
    nothing else; the admin site shows it read only and refuses changing it,
    because the next sync would put it back.
    """

    KIND_CHOICES = (
        ('bundle', _('bundle')),
        ('role', _('role')),
        ('status_action', _('status action')),
    )

    kind = models.CharField(_('kind'), max_length=16, choices=KIND_CHOICES)
    #: A bundle's name, a role's code, a status action's ``app_label.Model.code``.
    key = models.CharField(_('key'), max_length=255)

    class Meta:
        default_permissions = ()
        verbose_name = _('declared in code')
        verbose_name_plural = _('declared in code')
        constraints = (
            models.UniqueConstraint(fields=['kind', 'key'], name='clearance_declared_once'),
        )

    def __str__(self) -> str:
        return f'{self.kind}: {self.key}'

    @classmethod
    def holds(cls, kind: str, key: str) -> bool:
        """Whether the ``ACCESS`` file owns ``kind`` ``key``."""
        return cls.objects.filter(kind=kind, key=key).exists()

    @classmethod
    def keys(cls, kind: str) -> set[str]:
        """Everything of ``kind`` the ``ACCESS`` file owns."""
        return set(cls.objects.filter(kind=kind).values_list('key', flat=True))
