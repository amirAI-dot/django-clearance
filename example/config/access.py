"""
Who may do what in the shop, as code - applied by ``clearance_sync``, and by
every ``migrate`` (``SYNC_ON_MIGRATE``).

The file owns what it names: the admin site shows these bundles and roles
read only. Who is given a bundle or a role is not the file's to say - that is
done in the admin site, or by ``python manage.py example_data``.
"""

ACCESS = {
    'bundles': {
        # The orders of their own branch: read, edited and approved - never the price.
        'Branch managers': {
            'shop.order_view': 'branch',
            'shop.order_edit': 'branch',
            'shop.order_approve': 'branch',
            'shop.order_print_invoice': 'branch',
        },
        # Every order, with its price, and nothing changed.
        'Accountants': {
            'shop.order_view': 'all',
            'shop.order_view_price': None,
            'shop.order_print_invoice': 'all',
        },
        # Their own orders: read, and new ones placed for themselves.
        'Customers': {
            'shop.order_view': 'own',
            'shop.order_create': 'own',
        },
    },
    'roles': {
        # A customer starts with "Customers", and can never hold more than this.
        'customer': {
            'name': 'Customer',
            'ceiling': ['shop.order_view', 'shop.order_create'],
            'bundles': ['Customers'],
        },
        'manager': {
            'name': 'Branch manager',
            'ceiling': None,
            'bundles': ['Branch managers'],
        },
    },
}
