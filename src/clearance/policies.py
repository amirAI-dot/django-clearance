"""
Policies: the one place that answers "may this person do this?".

A policy is declared per resource, and its hooks - ``can_view``,
``can_edit``, ``can_approve`` - are what every view, service and command
asks. Two rules make them more than a codename check:

**A hook receives the object.** Holding ``loan_view`` need not mean seeing
every loan; a hook can add "and it is yours" by overriding, calling
``super()`` first so the codename is still required::

    class LoanPolicy(BasePolicy):
        app_label = 'loans'
        codename = 'loan'

        def can_view(self, user, obj=None):
            if not super().can_view(user, obj):
                return False
            return obj is None or obj.applicant_id == user.pk

**An action nobody wrote a hook for is refused.** Asking a policy about an
action it has no hook for raises, rather than answering yes or no: either
answer would be a guess, and the caller is a developer who misspelled
something.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, ClassVar, cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from clearance.protocols import User

#: A hook: the person, and the object when there is one.
Hook = Callable[[User, Any], bool]


class BasePolicy:
    """
    Maps an action to a decision.

    A subclass declares ``app_label`` and ``codename``; each hook then asks for
    ``{app_label}.{codename}_{action}``. ``custom_actions`` maps a view's
    action to the hook that authorises it - read by the bridges from a view to
    a policy, which refuse an action missing from it.
    """

    app_label: ClassVar[str] = ''
    codename: ClassVar[str] = ''
    custom_actions: ClassVar[Mapping[str, str]] = MappingProxyType({})

    #: What a hook's name starts with: the action ``approve`` is ``can_approve``.
    hook_prefix: ClassVar[str] = 'can_'

    @classmethod
    def check_declaration(cls) -> None:
        """
        Raise ``ImproperlyConfigured`` if this policy cannot work.

        Run when the policy is registered, at import time, so a policy that
        names no codename, or maps an action to a hook it does not have, fails
        the moment the project starts rather than the first time it is asked.
        """
        if not cls.app_label or not cls.codename:
            raise ImproperlyConfigured(f'{cls.__name__} must declare both app_label and codename.')

        for action, hook in cls.custom_actions.items():
            if not callable(getattr(cls, hook, None)):
                raise ImproperlyConfigured(
                    f'{cls.__name__}.custom_actions maps {action!r} to {hook}(), '
                    f'which {cls.__name__} does not have.'
                )

    # ------------------------------------------------------------------
    # Asking
    # ------------------------------------------------------------------

    def allows(self, user: User, action: str, obj: object | None = None) -> bool:
        """Whether ``user`` may do ``action``, to ``obj`` when there is one."""
        return bool(self.hook(action)(user, obj))

    def authorize(self, user: User, action: str, obj: object | None = None) -> None:
        """Raise Django's ``PermissionDenied`` unless ``user`` may do ``action``."""
        if not self.allows(user, action, obj):
            raise PermissionDenied

    def hook(self, action: str) -> Hook:
        """The hook that decides ``action``: ``approve`` -> ``can_approve``."""
        name = f'{self.hook_prefix}{action}'
        method = getattr(self, name, None)

        if not callable(method):
            raise ImproperlyConfigured(
                f'{type(self).__name__} has no {name}() to decide {action!r} with.'
            )

        return cast(Hook, method)

    def permission_for(self, action: str) -> str:
        """The permission ``action`` requires: ``loans.loan_approve``."""
        return f'{self.app_label}.{self.codename}_{action}'

    def has(self, user: User, action: str) -> bool:
        """
        Whether ``user`` holds the permission for ``action``.

        The building block every hook starts from. Asked without the object,
        because Django's own backend answers "no" to any permission asked
        about an object - object rules are the hooks' to add.
        """
        return bool(user.is_authenticated and user.has_perm(self.permission_for(action)))

    # ------------------------------------------------------------------
    # The standard hooks
    # ------------------------------------------------------------------

    def can_list(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'view')

    def can_view(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'view')

    def can_create(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'create')

    def can_edit(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'edit')

    def can_delete(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'delete')


class SignedInReadPolicy(BasePolicy):
    """
    Readable by anybody signed in; writable by permission.

    For reference data - the list of branches, the kinds of loan - that
    describes how a platform works rather than anything about a person.
    Gating its reads adds friction and protects nothing.
    """

    def can_list(self, user: User, obj: object | None = None) -> bool:
        return bool(user.is_authenticated and user.is_active)

    def can_view(self, user: User, obj: object | None = None) -> bool:
        return bool(user.is_authenticated and user.is_active)
