"""
The actions the admin site offers, found on every ``ModelAdmin`` registered.

An action the project wrote - ``actions = ['export_excel']`` - is decided by
its permission, ``<codename>_export_excel``, made on migrate. One that names
Django's own permissions (``@admin.action(permissions=['change'])``) is
Django's to decide, and ``delete_selected`` is the model's ``delete``:
neither is found, so no permission is made that nothing checks.
"""

from collections.abc import Iterator
from typing import Any

from django.contrib.admin.sites import all_sites

from clearance.admin.options import action_func, action_name
from clearance.discovery import ActionFinder, FoundAction
from clearance.registry import registry


class AdminActionFinder(ActionFinder):
    """The actions of every ``ModelAdmin`` on every admin site."""

    def find(self) -> Iterator[FoundAction]:
        for site in list(all_sites):
            for model, model_admin in site._registry.items():
                policy = registry.policy_for(model)
                admin_class = type(model_admin)

                guarded: Any = model_admin  # _get_base_actions: Django's, before any request

                for action in guarded._get_base_actions():
                    func, name = action_func(action), action_name(action)

                    if name == 'delete_selected' or getattr(func, 'allowed_permissions', None):
                        continue

                    origin = f'{admin_class.__module__}.{admin_class.__qualname__}.{name}'
                    yield FoundAction(policy, name, origin)
