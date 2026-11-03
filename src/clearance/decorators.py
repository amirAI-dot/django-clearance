"""
A function view, asking the policy::

    @policy_required(loan_access.policy, 'create')
    def apply(request):
        ...

The action-level check, as ``PolicyRequiredMixin`` makes it in ``dispatch``:
somebody not signed in is sent to the login page, and somebody signed in who
may not is answered 403. A view that judges one object asks once it has the
object - ``policy.authorize(request.user, 'approve', loan)``.

The action is checked when the view is decorated, at import: a policy with
no hook for it fails the project's start, not the first request.
"""

from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, TypeVar

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpRequest, HttpResponseBase

from clearance.policies import BasePolicy
from clearance.protocols import user_of

ViewT = TypeVar('ViewT', bound=Callable[..., HttpResponseBase])


def policy_required(policy: BasePolicy, action: str) -> Callable[[ViewT], ViewT]:
    """Let the view run only for somebody ``policy`` allows ``action``."""
    policy.hook(action)

    def decorator(view: ViewT) -> ViewT:
        if iscoroutinefunction(view):
            raise ImproperlyConfigured(
                f'policy_required decorates synchronous views; {view.__name__} is async.'
            )

        @wraps(view)
        def guarded(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
            user = user_of(request)

            if policy.allows(user, action):
                return view(request, *args, **kwargs)

            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            raise PermissionDenied

        return guarded  # type: ignore[return-value]

    return decorator
