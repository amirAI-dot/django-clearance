"""
The admin site, checked at start-up - registered when Django's admin is installed.

==================  =========================================================
``clearance.E016``  an admin site is not the library's: its pages would not
                    ask the policies, and would show every protected field
==================  =========================================================
"""

from collections.abc import Iterable
from typing import Any

from django.contrib.admin import AdminSite
from django.contrib.admin.sites import all_sites
from django.core.checks import CheckMessage, Error

from clearance.admin.sites import ClearanceAdminSite


def admin_site_errors(sites: Iterable[AdminSite]) -> list[CheckMessage]:
    """E016: every admin site is the library's, or one of its subclasses."""
    return [
        Error(
            f"The admin site {site.name!r} is {type(site).__name__}, not the library's: its "
            f'pages would not ask the policies, and would show every protected field.',
            hint="Put 'clearance.admin.apps.ClearanceAdminConfig' in INSTALLED_APPS in place "
            "of 'django.contrib.admin', and subclass ClearanceAdminSite for a site of your own.",
            obj=site,
            id='clearance.E016',
        )
        for site in sites
        if not isinstance(site, ClearanceAdminSite)
    ]


def check_admin_sites(app_configs: Any = None, **kwargs: Any) -> list[CheckMessage]:
    return admin_site_errors(sorted(all_sites, key=lambda site: site.name))


#: Every admin site check, registered by the app when Django's admin is installed.
CHECKS = (check_admin_sites,)
