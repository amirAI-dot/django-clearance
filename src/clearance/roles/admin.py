"""
Imported by Django's admin when it starts, as every app's ``admin`` module is:
the roles pages are mounted beside the access pages.
"""

from clearance.admin.sites import ClearanceAdminSite
from clearance.roles.pages import RolePages

ClearanceAdminSite.add_pages(RolePages)
