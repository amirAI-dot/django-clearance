"""
Authentication backends the suite installs to prove a point.

None is in the test project's settings: a test that needs one installs it for
itself, with ``override_settings``.
"""

from django.contrib.auth.backends import BaseBackend


class GrantsEverythingBackend(BaseBackend):
    """
    Grants every permission to every account - active or not.

    A project's own backend need not check ``is_active``, and Django asks
    every backend and grants when any one does. This is the worst case, for
    proving the library refuses a switched-off account by itself.
    """

    def has_perm(self, user_obj: object, perm: str, obj: object | None = None) -> bool:
        return True
