"""
Branches, people and orders to try the shop with - every password is the
username, so never on a real database.

    python manage.py example_data

Gives each person their role - the role gives them the bundle the ACCESS
file says it starts with - or, for the accountant, a bundle directly.
"""

from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from clearance.roles.models import Role
from clearance.roles.services import RoleService
from clearance.services import AccessService
from shop.models import Branch, Order, Person

PEOPLE = {
    # username: (branch, role, is_staff) - a role of None is given a bundle instead.
    'north_manager': ('North', 'manager', True),
    'south_manager': ('South', 'manager', True),
    'accountant': (None, None, True),
    'alice': (None, 'customer', False),
    'bob': (None, 'customer', False),
}

#: Bundles given to people directly, not through a role.
BUNDLES = {'accountant': 'Accountants'}

ORDERS = [
    ('alice', 'North', 'Desk lamp', 'pending', '45.00'),
    ('alice', 'South', 'Bookshelf', 'approved', '180.00'),
    ('bob', 'North', 'Office chair', 'pending', '240.00'),
    ('bob', 'South', 'Rug', 'delivered', '95.50'),
]


class Command(BaseCommand):
    help = 'Make branches, people and orders to try the example shop with.'

    @transaction.atomic
    def handle(self, *args, **options):
        branches = {name: Branch.objects.get_or_create(name=name)[0] for name in ('North', 'South')}
        roles, access = RoleService(actor=None), AccessService(actor=None)
        people = {}

        for username, (branch, role, staff) in PEOPLE.items():
            person, made = Person.objects.get_or_create(
                username=username,
                defaults={'branch': branches.get(branch), 'is_staff': staff},
            )
            if made:
                person.set_password(username)
                person.save()
                if role is not None:
                    roles.assign(person, Role.objects.get(code=role))
                if username in BUNDLES:
                    access.give_bundle(person, Group.objects.get(name=BUNDLES[username]))
            people[username] = person

        for customer, branch, item, status, price in ORDERS:
            Order.objects.get_or_create(
                customer=people[customer],
                item=item,
                defaults={'branch': branches[branch], 'status': status, 'price': Decimal(price)},
            )

        self.stdout.write(
            'Sign in at /admin/ as north_manager, south_manager, accountant, alice or bob - '
            'each password is the username. Make a superuser for the access pages.'
        )
