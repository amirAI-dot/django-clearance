"""Every change to a name, announced once it commits."""

from django.dispatch import Signal

#: ``thing``, ``language``, ``before``, ``after`` - each ``(name, description)``, or ``None``.
name_changed = Signal()
