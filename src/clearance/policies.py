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

**A hook respects the row scopes.** Handed an object of a scoped model,
``can_edit`` requires the permission *and* the object within the person's
``edit`` scope - so a hook never allows what ``visible_to`` would hide.

**A model with no policy of its own** is asked through a ``ModelPolicy``,
made by the registry from the model's permissions alone.

**An action nobody wrote a hook for is decided by its permission** and its
scope, as the standard four are: ``print_invoice`` needs
``shop.order_print_invoice``, and the object within its scope. Its permission
is made on ``migrate`` when a view asks for it (``clearance.actions``), and
held by nobody until given - so a misspelled action is refused to everybody,
and shows in the admin site under the name it was misspelled with. A name
that could never be a permission - ``Approve!`` - raises instead.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, ClassVar, cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Model

from clearance import permissions
from clearance.protocols import User

#: A hook: the person, and the object when there is one.
Hook = Callable[[User, Any], bool]


class BasePolicy:
    """
    Maps an action to a decision.

    A subclass names its ``model``, or declares ``app_label`` and ``codename``
    for a resource that is not one model. Each hook then asks for the
    permission ``permissions.permission_for`` names - in Django's style or the
    library's, whichever the model keeps. ``custom_actions`` maps a view's
    action to the hook that decides it, when the two are named differently -
    ``{'approve_all': 'can_approve'}``.
    """

    #: The model this policy decides about. Its app label and name are the defaults.
    model: ClassVar[type[Model] | None] = None
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
        if cls.model is None and cls.app_label and cls.codename:
            cls.model = _model_named(cls.app_label, cls.codename)

        if cls.model is not None:
            cls.app_label = cls.app_label or cls.model._meta.app_label
            cls.codename = cls.codename or cls.model._meta.model_name or ''

        if not cls.app_label or not cls.codename:
            raise ImproperlyConfigured(
                f'{cls.__name__} must name its model, or declare both app_label and codename.'
            )

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
        """
        The hook that decides ``action``: the one ``custom_actions`` maps it
        to, ``can_approve`` for ``approve`` when the policy has one, and
        otherwise the action's permission within its scope.
        """
        method = getattr(self, self.hook_name(action), None)

        if callable(method):
            return cast(Hook, method)

        if not permissions.is_action_name(action):
            raise ImproperlyConfigured(
                f'{type(self).__name__} cannot decide {action!r}: an action is lowercase words '
                f"joined by underscores, and is the end of a permission's name."
            )

        def by_permission(user: User, obj: object | None = None) -> bool:
            return self.has_within_scope(user, action, obj)

        return by_permission

    def hook_name(self, action: str) -> str:
        """The name of the method that would decide ``action``, whether or not it exists."""
        return self.custom_actions.get(action, f'{self.hook_prefix}{action}')

    def permission_for(self, action: str) -> str:
        """The permission ``action`` requires: ``shop.change_order``, ``loans.loan_approve``."""
        if self.model is not None:
            return permissions.permission_for(self.model, action, codename=self.codename)
        return f'{self.app_label}.{self.codename}_{"view" if action == "list" else action}'

    def has(self, user: User, action: str) -> bool:
        """
        Whether ``user`` holds the permission for ``action``.

        The building block every hook starts from, so it refuses anybody not
        signed in and any account switched off, itself. Django's own backend
        refuses an inactive account too, but ``has_perm`` asks every backend
        and grants when any one does - and a project's own backend need not
        look at ``is_active``. A switched-off account must hold nothing,
        whatever is installed.

        Asked without the object, because Django's own backend answers "no"
        to any permission asked about an object - object rules are the hooks'
        to add.
        """
        return bool(
            user.is_authenticated and user.is_active and user.has_perm(self.permission_for(action))
        )

    def within_scope(self, user: User, action: str, obj: object | None) -> bool:
        """
        Whether ``obj`` is among the rows ``user`` reaches for ``action``.

        True when there is no object, or the person reaches every row of its
        model. Otherwise one ``exists()``: the same question ``visible`` answers
        for a list, asked about one row.
        """
        from clearance.querysets import EVERY_ROW, answers_for_itself, scopes_reaching, visible

        if not isinstance(obj, Model):
            return True

        if getattr(user, 'is_superuser', False) and user.is_active:
            return True

        rows = type(obj)._default_manager.all()

        if answers_for_itself(rows):  # its own visible_to says, not its grants
            return bool(visible(rows, user, action).filter(pk=obj.pk).exists())

        names = scopes_reaching(rows, user, action)

        if names is None:
            return False

        if EVERY_ROW in names:
            return True

        return bool(visible(rows, user, action).filter(pk=obj.pk).exists())

    def has_within_scope(self, user: User, action: str, obj: object | None) -> bool:
        """The permission for ``action``, and ``obj`` within its scope: every standard hook."""
        return self.has(user, action) and self.within_scope(user, action, obj)

    # ------------------------------------------------------------------
    # The standard hooks
    # ------------------------------------------------------------------

    def can_list(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'view')

    def can_view(self, user: User, obj: object | None = None) -> bool:
        return self.has_within_scope(user, 'view', obj)

    def can_create(self, user: User, obj: object | None = None) -> bool:
        return self.has(user, 'create')

    def can_edit(self, user: User, obj: object | None = None) -> bool:
        return self.has_within_scope(user, 'edit', obj)

    def can_delete(self, user: User, obj: object | None = None) -> bool:
        return self.has_within_scope(user, 'delete', obj)


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


def _model_named(app_label: str, codename: str) -> type[Model] | None:
    """
    The model a policy's ``app_label`` and ``codename`` name, if they name one.

    So a policy that says ``shop`` and ``order`` asks for the permissions
    ``Order`` actually keeps - Django's ``change_order`` or the library's
    ``order_edit`` - rather than guessing from the names.
    """
    from django.apps import apps

    try:
        return apps.get_model(app_label, codename)
    except (LookupError, ValueError):
        return None


class ModelPolicy(BasePolicy):
    """
    The policy of a model nobody wrote one for: its permissions and its scopes.

    Made by the registry, one per model, on first use - so every model is
    asked the same way whether or not its project wrote a policy for it.
    """

    @classmethod
    def for_model(cls, model: type[Model]) -> 'ModelPolicy':
        policy_class = cast(
            type[ModelPolicy], type(f'{model.__name__}Policy', (cls,), {'model': model})
        )
        policy_class.check_declaration()
        return policy_class()
