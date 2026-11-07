"""
Every change to roles, announced - sent by ``RoleService`` once the change
commits, each with ``actor`` and what changed.
"""

from django.dispatch import Signal

#: ``role``, ``created`` - whether it is new.
role_saved = Signal()
#: ``code``, ``name``.
role_deleted = Signal()
#: ``person``, ``role``.
role_assigned = Signal()
#: ``person``, ``role``.
role_unassigned = Signal()
#: ``role``, ``before``, ``after`` - each the permissions it allows, or ``None`` for no ceiling.
ceiling_changed = Signal()
