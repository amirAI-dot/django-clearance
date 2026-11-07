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
