"""Which orders a grant reaches: the scopes the code offers beside the admin site's."""

from types import MappingProxyType

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from clearance.querysets import ScopedQuerySet


class OrderQuerySet(ScopedQuerySet):
    scopes = MappingProxyType(
        {
            'own': _('Their own orders'),
            'branch': _("Their branch's orders"),
        }
    )

    def scope_own(self, user):
        return Q(customer=user)

    def scope_branch(self, user):
        return Q(branch=getattr(user, 'branch_id', None))
