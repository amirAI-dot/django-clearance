"""
Every change to access, announced - for a project's own audit trail.

Each is sent by ``AccessService`` after the transaction commits, so a
receiver never records a change that was rolled back. Every one carries
``actor`` - who made the change, ``None`` for the system - and what changed.
"""

from django.dispatch import Signal

#: ``bundle``, ``grants`` - ``{permission: scope}``.
bundle_created = Signal()
#: ``bundle``, ``before``, ``after`` - each ``{permission: scope}`` - and ``name``.
bundle_changed = Signal()
#: ``name``, ``grants``, ``people`` - whom it reached.
bundle_deleted = Signal()
#: ``person``, ``bundle``.
bundle_given = Signal()
#: ``person``, ``bundle``.
bundle_taken = Signal()
#: ``person``, ``permission``, ``scope``.
permission_granted = Signal()
#: ``person``, ``permission``, ``reason``.
permission_revoked = Signal()
#: ``person``, ``permission``.
permission_restored = Signal()
#: ``person``, ``permission``, ``before``, ``after``.
scope_changed = Signal()
#: ``rule``, ``created`` - whether it is new.
scope_rule_saved = Signal()
#: ``model``, ``code``, ``name``.
scope_rule_deleted = Signal()
#: ``model``, ``field``, ``permissions`` - ``{'view': ..., 'edit': ...}``, just made.
field_protected = Signal()
#: ``model``, ``field``, ``permissions`` - the two deleted with it.
field_unprotected = Signal()
#: ``action``, ``created`` - whether it is new.
status_action_saved = Signal()
#: ``model``, ``code``, ``name``.
status_action_deleted = Signal()
#: ``permissions`` - those ``migrate`` just made for actions found in the code.
actions_found = Signal()
