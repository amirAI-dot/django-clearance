"""
What the library adds to Django's own permission tables.

A bundle is Django's ``Group``, a person's bundles are ``user.groups``, and a
permission is an ``auth_permission`` row; none of that is copied here. These
tables hold only what Django has no place for: the scope a permission is
given with, a permission taken away from one person, the scopes an
administrator builds from rules, the fields they protect, the status
actions they make - and which of all that the ``ACCESS`` file owns.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
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


class ScopeRuleQuerySet(models.QuerySet['ScopeRule']):
    def with_conditions(self) -> 'ScopeRuleQuerySet':
        """Each rule with its conditions and their values - two queries more, however many."""
        return self.prefetch_related('condition_rows__value_rows')

    def read(self) -> list[tuple[str, str, list[dict[str, Any]]]]:
        """
        ``(code, match, conditions)`` of every rule here, in one query - a row
        per constant, joined. A rule with no condition has nothing to read:
        ``clearance_check`` lists it.
        """
        found: dict[int, tuple[str, str, dict[int, tuple[ScopeCondition, list[str]]]]] = {}
        rows = (
            ScopeCondition.objects.filter(rule__in=self)
            .order_by('rule', 'position', 'value_rows__position')
            .values_list(
                'rule',
                'rule__code',
                'rule__match',
                'position',
                'field',
                'operator',
                'source',
                'person',
                'value_rows__value',
            )
        )

        for rule, code, match, position, field, operator, source, person, value in rows:
            _, _, conditions = found.setdefault(rule, (code, match, {}))
            _condition, values = conditions.setdefault(
                position,
                (ScopeCondition(field=field, operator=operator, source=source, person=person), []),
            )
            if value is not None:
                values.append(value)

        return [
            (code, match, [row.as_condition(values) for row, values in conditions.values()])
            for code, match, conditions in found.values()
        ]


class ScopeRule(models.Model):
    """
    A row scope an administrator built, from rules - offered beside the code's.

    Its conditions are ``ScopeCondition`` rows, joined by ``match``: ``all`` of
    them, or ``any``. They are checked against the model whenever the rule is
    saved (``clearance.rules``), and turned into a ``Q`` when a list is asked
    for.

    ``conditions`` reads and sets them as ``clearance.rules`` reads them - a list
    of ``{'field': ..., 'operator': ..., 'value': ...}``. Conditions set are
    written when the rule is saved, in the same transaction, in place of the
    ones it had.
    """

    MATCH_CHOICES = (('all', _('all of the conditions')), ('any', _('any of the conditions')))

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+', verbose_name=_('model')
    )
    code = models.CharField(_('code'), max_length=64)
    name = models.CharField(_('name'), max_length=160)
    match = models.CharField(_('match'), max_length=3, choices=MATCH_CHOICES, default='all')

    objects = ScopeRuleQuerySet.as_manager()

    #: The conditions set and not yet saved - ``None`` once they are.
    _unsaved_conditions: Any = None

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

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic(using=kwargs.get('using')):
            super().save(*args, **kwargs)

            if self._unsaved_conditions is not None:
                ScopeCondition.write(self, self._unsaved_conditions)
                self._unsaved_conditions = None

    @property
    def conditions(self) -> list[dict[str, Any]]:
        """The conditions as ``clearance.rules`` reads them: set ones until they are saved."""
        if self._unsaved_conditions is not None:
            return self._unsaved_conditions  # type: ignore[no-any-return]
        if self.pk is None:
            return []
        return [row.as_condition() for row in self.condition_rows.all()]

    @conditions.setter
    def conditions(self, conditions: Sequence[Mapping[str, Any]]) -> None:
        self._unsaved_conditions = conditions

    @staticmethod
    def stored_form(conditions: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """``conditions`` as they read once saved - every constant in words."""
        return [
            ScopeCondition.of(None, 0, item).as_condition(_constants_of(item))
            for item in conditions
        ]

    def compiled(self, protection: 'Protection | None' = None) -> 'Rule':
        """The rule, checked against its model - and what is protected - as they are now."""
        from clearance.rules import Rule

        model = self.content_type.model_class()

        if model is None:
            from django.core.exceptions import ValidationError

            raise ValidationError('The model of this rule no longer exists.')

        return Rule.parse(model, self.match, self.conditions, protection=protection)


class ScopeCondition(models.Model):
    """
    One condition of a rule scope: a field, an operator, and where its value
    comes from - a constant, a list of them, something of the person's, or
    nothing at all (``is_empty``). Constants are ``ScopeConditionValue`` rows.
    """

    SOURCE_CHOICES = (
        ('constant', _('a constant')),
        ('list', _('a list of constants')),
        ('person', _("something of the person's")),
        ('none', _('no value')),
    )

    rule = models.ForeignKey(
        ScopeRule, on_delete=models.CASCADE, related_name='condition_rows', verbose_name=_('rule')
    )
    position = models.PositiveSmallIntegerField(_('position'))
    field = models.CharField(_('field'), max_length=255)
    operator = models.CharField(_('operator'), max_length=32)
    source = models.CharField(_('value from'), max_length=8, choices=SOURCE_CHOICES)
    #: The path of the person's field when ``source`` is ``person`` - empty is the person.
    person = models.CharField(_("the person's field"), max_length=255, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ('position',)
        verbose_name = _('scope condition')
        verbose_name_plural = _('scope conditions')
        constraints = (
            models.UniqueConstraint(
                fields=['rule', 'position'], name='clearance_scopecondition_one_per_position'
            ),
        )

    def __str__(self) -> str:
        return f'{self.field} {self.operator}'

    @classmethod
    def of(cls, rule: ScopeRule | None, position: int, item: Mapping[str, Any]) -> 'ScopeCondition':
        """The row ``item`` - a condition as ``clearance.rules`` reads it - is stored as."""
        item = item if isinstance(item, Mapping) else {}
        value = item.get('value')
        value = value if isinstance(value, Mapping) else {}

        if 'person' in value:
            source, person = 'person', str(value['person'])
        elif 'constant' in value:
            source, person = ('list' if isinstance(value['constant'], list) else 'constant'), ''
        else:
            source, person = 'none', ''

        return cls(
            rule=rule,
            position=position,
            field=str(item.get('field', '')),
            operator=str(item.get('operator', '')),
            source=source,
            person=person,
        )

    @classmethod
    def write(cls, rule: ScopeRule, conditions: Iterable[Mapping[str, Any]]) -> None:
        """Put ``conditions`` in place of the ones ``rule`` has - in three queries."""
        conditions = list(conditions)
        rule.condition_rows.all().delete()
        rows = ScopeCondition.objects.bulk_create(
            [ScopeCondition.of(rule, position, item) for position, item in enumerate(conditions)]
        )
        ScopeConditionValue.objects.bulk_create(
            ScopeConditionValue(condition=row, position=position, value=_word(constant))
            for row, item in zip(rows, conditions, strict=True)
            for position, constant in enumerate(_constants_of(item))
        )
        getattr(rule, '_prefetched_objects_cache', {}).pop('condition_rows', None)

    def as_condition(self, values: Sequence[str] | None = None) -> dict[str, Any]:
        """This condition as ``clearance.rules`` reads it."""
        condition: dict[str, Any] = {'field': self.field, 'operator': self.operator}
        constants = (
            list(values) if values is not None else [row.value for row in self.value_rows.all()]
        )

        if self.source == 'person':
            condition['value'] = {'person': self.person}
        elif self.source == 'list':
            condition['value'] = {'constant': constants}
        elif self.source == 'constant':
            condition['value'] = {'constant': constants[0] if constants else None}

        return condition


class ScopeConditionValue(models.Model):
    """A constant a condition compares with - one, or each of a list, in its order."""

    condition = models.ForeignKey(
        ScopeCondition,
        on_delete=models.CASCADE,
        related_name='value_rows',
        verbose_name=_('condition'),
    )
    position = models.PositiveSmallIntegerField(_('position'))
    #: In words - the field reads it in its own type; empty is no value.
    value = models.TextField(_('value'), blank=True)

    class Meta:
        default_permissions = ()
        ordering = ('position',)
        verbose_name = _('scope condition value')
        verbose_name_plural = _('scope condition values')
        constraints = (
            models.UniqueConstraint(
                fields=['condition', 'position'],
                name='clearance_scopeconditionvalue_one_per_position',
            ),
        )

    def __str__(self) -> str:
        return str(self.value)


def _constants_of(item: Mapping[str, Any]) -> list[str]:
    """The constants a condition compares with, in words."""
    value = item.get('value') if isinstance(item, Mapping) else None

    if not isinstance(value, Mapping) or 'person' in value or 'constant' not in value:
        return []

    constant = value['constant']
    return [_word(one) for one in (constant if isinstance(constant, list) else [constant])]


def _word(value: object) -> str:
    return '' if value is None else str(value)


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


class StatusActionQuerySet(models.QuerySet['StatusAction']):
    def with_values(self) -> 'StatusActionQuerySet':
        """Each action with its values - one query more, however many."""
        return self.prefetch_related('value_rows')


class StatusAction(models.Model):
    """
    An action an administrator made that writes values: ``approve`` sets
    ``status`` to ``approved`` or ``rejected``, from ``pending``.

    Its permission - ``<codename>_<code>`` - is made with it and deleted with
    it. A status action declared in code (``build_permissions(status_actions=
    ...)``) has no row here; ``clearance.actions`` reads both.

    Its values are ``StatusActionValue`` rows; ``to_values`` and
    ``from_values`` read and set them, in words, and values set are written
    when the action is saved, in the same transaction.
    """

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name='+', verbose_name=_('model')
    )
    code = models.CharField(_('code'), max_length=64)
    name = models.CharField(_('name'), max_length=160)
    field = models.CharField(_('field'), max_length=64)

    objects = StatusActionQuerySet.as_manager()

    #: The values set and not yet saved, by end - empty once they are.
    _unsaved_values: Any = None

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

    def save(self, *args: Any, **kwargs: Any) -> None:
        with transaction.atomic(using=kwargs.get('using')):
            super().save(*args, **kwargs)

            if self._unsaved_values:
                StatusActionValue.write(self, self._unsaved_values)
                self._unsaved_values = None

    @property
    def to_values(self) -> list[str]:
        """The values only this action writes."""
        return self._values(StatusActionValue.TO)

    @to_values.setter
    def to_values(self, values: Iterable[object]) -> None:
        self._set(StatusActionValue.TO, values)

    @property
    def from_values(self) -> list[str]:
        """The values it may write them from; empty is from any value."""
        return self._values(StatusActionValue.FROM)

    @from_values.setter
    def from_values(self, values: Iterable[object]) -> None:
        self._set(StatusActionValue.FROM, values)

    def _values(self, end: str) -> list[str]:
        if self._unsaved_values and end in self._unsaved_values:
            return list(self._unsaved_values[end])
        if self.pk is None:
            return []
        return [row.value for row in self.value_rows.all() if row.end == end]

    def _set(self, end: str, values: Iterable[object]) -> None:
        self._unsaved_values = {**(self._unsaved_values or {}), end: [str(v) for v in values]}


class StatusActionValue(models.Model):
    """A value a status action writes, or writes from - in words, read in the field's type."""

    TO, FROM = 'to', 'from'
    END_CHOICES = ((TO, _('writes')), (FROM, _('writes from')))

    action = models.ForeignKey(
        StatusAction,
        on_delete=models.CASCADE,
        related_name='value_rows',
        verbose_name=_('status action'),
    )
    end = models.CharField(_('end'), max_length=4, choices=END_CHOICES)
    position = models.PositiveSmallIntegerField(_('position'))
    value = models.CharField(_('value'), max_length=255)

    class Meta:
        default_permissions = ()
        ordering = ('end', 'position')
        verbose_name = _('status action value')
        verbose_name_plural = _('status action values')
        constraints = (
            models.UniqueConstraint(
                fields=['action', 'end', 'value'], name='clearance_statusactionvalue_once_each'
            ),
        )

    def __str__(self) -> str:
        return f'{self.end} {self.value}'

    @classmethod
    def write(cls, action: StatusAction, values: Mapping[str, Sequence[str]]) -> None:
        """Put ``values`` - by end - in place of the ones ``action`` has at those ends."""
        action.value_rows.filter(end__in=list(values)).delete()
        StatusActionValue.objects.bulk_create(
            StatusActionValue(action=action, end=end, position=position, value=value)
            for end, words in values.items()
            for position, value in enumerate(dict.fromkeys(words))
        )
        getattr(action, '_prefetched_objects_cache', {}).pop('value_rows', None)


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
