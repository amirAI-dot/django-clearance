"""
Imported by Django's admin when it starts: the names page is mounted beside
the access pages.
"""

from clearance.admin.sites import ClearanceAdminSite
from clearance.translations.pages import NamePages

ClearanceAdminSite.add_pages(NamePages)
