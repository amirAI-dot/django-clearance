"""
Declaring a resource's permissions, on its model.

A guarded resource declares its permissions in ``Meta.permissions``, so
``migrate`` creates the rows like any other permission and nothing has to be
synchronised::

    class Loan(models.Model):
        class Meta:
            default_permissions = ()
            permissions = build_permissions('loan', _('loans'), actions=('view', 'approve'))

``default_permissions = ()`` turns off Django's own add/change/delete/view,
which would otherwise sit beside these as a second answer to the same
question - one that no policy ever asks.

**A model that declares nothing keeps Django's own permissions** -
``view_order``, ``add_order``, ``change_order``, ``delete_order`` - and
``permission_for`` answers in that style for it, so nothing anywhere spells a
permission's name by hand.

**The name written to the database is always English.** ``migrate`` stores it
in ``auth_permission.name`` once. A resource name marked for translation
would otherwise be resolved in whatever language was active when the model
was imported, baking it into the migration state - and ``makemigrations``
would then report changes on models nobody touched. So the stored name is
worked out with translation switched off, and the reader's language is
``PermissionSet.label``'s job.
"""

import re
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Final

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

#: The actions every guarded resource supports unless it says otherwise.
DEFAULT_ACTIONS: Final = ('view', 'create', 'edit', 'delete')

#: A record that is read, written and corrected, but never deleted. Offering
#: a ``delete`` permission on it would be a power that does nothing - shown in
#: every permission screen, granted to people, and refused by the policy.
RECORD_ACTIONS: Final = ('view', 'create', 'edit')

#: How an action reads, for the actions every resource has. Any other action
#: reads as its own words - ``look_up`` is "Can look up loans" - unless the
#: resource gives it a label of its own.
ACTION_LABELS: Final[Mapping[str, str | Promise]] = MappingProxyType(
    {
        'view': _('Can view %(resource)s'),
        'create': _('Can create %(resource)s'),
        'edit': _('Can edit %(resource)s'),
        'delete': _('Can delete %(resource)s'),
    }
)

#: A codename or an action: lowercase words joined by underscores. The
#: ``app_label.codename_action`` a policy asks for is built from these, and a
#: space or a dot in one would build a permission nobody can ever hold.
_NAME = re.compile(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*')


class PermissionSet:
    """
    The permissions one resource declares: a codename and its actions.

    ``entries()`` is what goes in ``Meta.permissions``. The rest is for whoever
    reads a permission back - ``label`` says it in the reader's language.
    """

    def __init__(
        self,
        codename: str,
        resource: str | Promise,
        *,
        actions: Iterable[str] = DEFAULT_ACTIONS,
        labels: Mapping[str, str | Promise] | None = None,
    ) -> None:
        self.codename = codename
        self.resource = resource
        self.actions = tuple(actions)
        self.labels: Mapping[str, str | Promise] = MappingProxyType(
            {**ACTION_LABELS, **(labels or {})}
        )
        self._validate()

    def codename_for(self, action: str) -> str:
        """``view`` -> ``loan_view``."""
        return f'{self.codename}_{action}'

    def label(self, action: str) -> str:
        """How ``action`` reads in the active language."""
        template = self.labels.get(action)

        if template is None:
            words = action.replace('_', ' ')
            return f'Can {words} {self.resource}'

        return str(template) % {'resource': str(self.resource)}

    def stored_name(self, action: str) -> str:
        """How ``action`` reads in English: what ``migrate`` writes."""
        with translation.override(None):
            return self.label(action)

    def entries(self) -> tuple[tuple[str, str], ...]:
        """``(codename, name)`` for every action - ``Meta.permissions``."""
        return tuple(
            (self.codename_for(action), self.stored_name(action)) for action in self.actions
        )

    def _validate(self) -> None:
        if not _NAME.fullmatch(self.codename):
            raise ImproperlyConfigured(
                f'{self.codename!r} is not a codename: use lowercase words joined by underscores.'
            )

        if not self.actions:
            raise ImproperlyConfigured(f'{self.codename!r} declares no actions.')

        for action in self.actions:
            if not _NAME.fullmatch(action):
                raise ImproperlyConfigured(
                    f'{action!r} is not an action: use lowercase words joined by underscores.'
                )

        repeated = sorted({action for action in self.actions if self.actions.count(action) > 1})

        if repeated:
            raise ImproperlyConfigured(
                f'{self.codename!r} declares {", ".join(repeated)} more than once.'
            )

        unknown = sorted(set(self.labels) - set(ACTION_LABELS) - set(self.actions))

        if unknown:
            raise ImproperlyConfigured(
                f'{self.codename!r} labels actions it does not declare: {", ".join(unknown)}.'
            )


def build_permissions(
    codename: str,
    resource: str | Promise,
    *,
    actions: Iterable[str] = DEFAULT_ACTIONS,
    labels: Mapping[str, str | Promise] | None = None,
) -> tuple[tuple[str, str], ...]:
    """
    ``Meta.permissions`` for one resource.

    ``build_permissions('loan', 'loans')`` gives ``loan_view``, ``loan_create``,
    ``loan_edit`` and ``loan_delete``. ``labels`` names an action in words of
    its own - ``{'approve': _('Can approve or decline %(resource)s')}``.
    """
    return PermissionSet(codename, resource, actions=actions, labels=labels).entries()


#: Django's own verb for each of the four actions every model has.
DJANGO_VERBS: Final[Mapping[str, str]] = MappingProxyType(
    {'view': 'view', 'create': 'add', 'edit': 'change', 'delete': 'delete'}
)


def permission_for(model: type[Model] | Model, action: str, *, codename: str | None = None) -> str:
    """
    The permission ``action`` on ``model`` needs, as ``app_label.codename``.

    A model keeping Django's permissions answers in Django's style -
    ``shop.change_order`` for ``edit``; a model that declares its own answers
    in the library's - ``shop.order_edit``. Listing is viewing. An action
    beyond the four is ``<codename>_<action>`` either way. ``codename`` names
    the resource when it is not the model's own name.
    """
    meta = model._meta
    action = 'view' if action == 'list' else action
    verb = DJANGO_VERBS.get(action)

    if verb is not None and verb in meta.default_permissions:
        return f'{meta.app_label}.{verb}_{meta.model_name}'

    return f'{meta.app_label}.{codename or meta.model_name}_{action}'
