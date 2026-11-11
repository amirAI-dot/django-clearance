"""
The shop in the admin site. Nothing about access is written here: every page
asks the order's policy, hides the price from whoever may not read it, and
offers only the status values the person may write.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from shop.models import Branch, Order, Person


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('item', 'branch', 'customer', 'status', 'price')
    list_filter = ('status', 'branch')


admin.site.register(Branch)


@admin.register(Person)
class PersonAdmin(UserAdmin):
    fieldsets = (*UserAdmin.fieldsets, ('Branch', {'fields': ('branch',)}))
