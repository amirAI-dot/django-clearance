"""
Actions found in the code: an action that does something new - prints an
invoice, exports a sheet - decided by its permission, with no code for it.

    class OrderPrintView(PolicyRequiredMixin, DetailView):
        policy_action = 'print_invoice'          # shop.order_print_invoice

    @policy_required(order_access.policy, 'refund')
    def refund(request, pk): ...                 # shop.order_refund

``migrate`` finds every one in the URLconf and makes its permission, held by
nobody until given. An action a policy wrote a hook for is the hook's: its
permission, if it has one, is declared with the model - making one here
would be a permission nothing checks.

Finding is done by ``ActionFinder``s, one per kind of code, so the DRF and
admin site doors add theirs without anything here changing.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Model

from clearance import signals
from clearance.actions import STANDARD_ACTIONS
from clearance.permissions import is_action_name
from clearance.policies import BasePolicy
from clearance.views import PolicyRequiredMixin, urlconf_callbacks

logger = logging.getLogger('clearance')

#: The longest codename ``auth_permission`` holds.
_CODENAME_LENGTH = 100


@dataclass(frozen=True)
class FoundAction:
    """An action some code asks a policy about, decided by its permission alone."""

    policy: BasePolicy
    action: str
    #: Where it was found: ``app.views.OrderPrintView``.
    origin: str

    @property
    def model(self) -> type[Model] | None:
        return self.policy.model

    @property
    def permission(self) -> str:
        return self.policy.permission_for(self.action)


class ActionFinder(ABC):
    """Finds the actions one kind of code asks for."""

    @abstractmethod
    def find(self) -> Iterator[FoundAction]: ...


class ViewFinder(ActionFinder):
    """Django's views in the URLconf: a ``PolicyRequiredMixin`` view, a ``@policy_required`` one."""

    def find(self) -> Iterator[FoundAction]:
        for callback in urlconf_callbacks():
            view_class = getattr(callback, 'view_class', None)

            if isinstance(view_class, type) and issubclass(view_class, PolicyRequiredMixin):
                policy, action = view_class.resolved_policy(), view_class.resolved_action()
                origin = f'{view_class.__module__}.{view_class.__qualname__}'
            else:
                policy = getattr(callback, 'clearance_policy', None)
                action = getattr(callback, 'clearance_action', None)
                origin = f'{callback.__module__}.{callback.__qualname__}'

            if isinstance(policy, BasePolicy) and action is not None:
                yield FoundAction(policy, action, origin)


#: Every finder ``find_actions`` asks, in order.
FINDERS: tuple[ActionFinder, ...] = (ViewFinder(),)


def find_actions(finders: Iterable[ActionFinder] = FINDERS) -> list[FoundAction]:
    """
    Every action found, once each: not one of the four every model has, not
    one a policy wrote a hook for, and a name that can end a permission's.
    """
    found: dict[tuple[type, str], FoundAction] = {}

    for finder in finders:
        for action in finder.find():
            hook = getattr(action.policy, f'{action.policy.hook_prefix}{action.action}', None)

            if action.action in STANDARD_ACTIONS or callable(hook):
                continue

            if is_action_name(action.action):
                found.setdefault((type(action.policy), action.action), action)

    return list(found.values())


def action_problems(action: FoundAction) -> str | None:
    """Why ``action``'s permission cannot be made, or ``None``: E013."""
    if action.model is None:
        return (
            f'{action.origin} asks for {action.action!r}, but its policy has no model to keep '
            f'the permission on. Declare {action.permission} with a model.'
        )

    if len(action.permission.partition('.')[2]) > _CODENAME_LENGTH:
        return f'{action.origin}: {action.permission} is longer than a permission can be.'

    return None


def make_found_permissions(
    found: Iterable[FoundAction], using: str = DEFAULT_DB_ALIAS
) -> list[str]:
    """Make the permission of every action found that has none yet; the names made."""
    made = []

    for action in found:
        model = action.model

        if model is None or action_problems(action) is not None:
            continue

        content_type = ContentType.objects.db_manager(using).get_for_model(model)
        _, created = Permission.objects.db_manager(using).get_or_create(
            content_type=content_type,
            codename=action.permission.partition('.')[2],
            defaults={'name': action_label(model, action.action)},
        )

        if created:
            made.append(action.permission)

    return made


def action_label(model: type[Model], action: str) -> str:
    """How an action's permission reads in English: what is stored."""
    return f'Can {action.replace("_", " ")} {model._meta.verbose_name_plural}'


def make_permissions_after_migrate(
    sender: object, using: str = DEFAULT_DB_ALIAS, verbosity: int = 1, **kwargs: Any
) -> None:
    """``post_migrate``: make the permission of every action found in the code."""
    try:
        found = find_actions()
    except Exception:
        # A URLconf that does not import is Django's own check to report.
        logger.warning('No actions were found: the URLconf could not be read.', exc_info=True)
        return

    made = make_found_permissions(found, using)

    if made and verbosity >= 2:
        print(f'Made the permissions of actions found in the code: {", ".join(made)}')

    if made:
        signals.actions_found.send(sender=sender, actor=None, permissions=made)
