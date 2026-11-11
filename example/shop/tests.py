"""
The shop does what its README says - run with ``python manage.py test``.

If these fail, the example teaches something the library does not do: a
manager reads another branch's orders, a price shows to somebody without its
permission, a customer approves their own order, or a delivered order is
edited.
"""

import io

from django.core.management import call_command
from django.test import TestCase

from shop.models import Order, Person


class TheShop(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('clearance_sync', verbosity=0)
        call_command('example_data', stdout=io.StringIO())

    def sign_in(self, username):
        self.client.force_login(Person.objects.get(username=username))

    def orders(self):
        return {row['item']: row for row in self.client.get('/api/orders/').json()}

    # ------------------------------------------------------------ who sees what

    def test_a_manager_reads_their_branchs_orders_without_the_price(self):
        self.sign_in('north_manager')

        orders = self.orders()

        self.assertEqual(set(orders), {'Desk lamp', 'Office chair'})
        self.assertNotIn('price', orders['Desk lamp'])

    def test_an_accountant_reads_every_order_with_its_price(self):
        self.sign_in('accountant')

        orders = self.orders()

        self.assertEqual(len(orders), 4)
        self.assertEqual(orders['Rug']['price'], '95.50')

    def test_a_customer_reads_only_their_own_orders(self):
        self.sign_in('alice')

        self.assertEqual(set(self.orders()), {'Desk lamp', 'Bookshelf'})

    def test_the_orders_page_shows_the_same_rows_and_hides_the_price(self):
        self.sign_in('north_manager')

        page = self.client.get('/orders/').content.decode()

        self.assertIn('Office chair', page)
        self.assertNotIn('Bookshelf', page)
        self.assertNotIn('240.00', page)

    def test_somebody_signed_out_is_refused(self):
        self.assertEqual(self.client.get('/api/orders/').status_code, 403)

    # ------------------------------------------------------------ what they may do

    def test_a_manager_approves_a_pending_order_of_their_branch(self):
        self.sign_in('north_manager')
        lamp = Order.objects.get(item='Desk lamp')

        answer = self.client.patch(
            f'/api/orders/{lamp.pk}/', {'status': 'approved'}, content_type='application/json'
        )

        self.assertEqual(answer.status_code, 200)
        lamp.refresh_from_db()
        self.assertEqual(lamp.status, 'approved')

        again = self.client.patch(
            f'/api/orders/{lamp.pk}/', {'status': 'rejected'}, content_type='application/json'
        )
        self.assertEqual(again.status_code, 400, 'approving writes only from pending')

    def test_another_branchs_order_does_not_exist_for_them(self):
        self.sign_in('north_manager')
        shelf = Order.objects.get(item='Bookshelf')

        answer = self.client.patch(
            f'/api/orders/{shelf.pk}/', {'item': 'Shelf'}, content_type='application/json'
        )

        self.assertEqual(answer.status_code, 404)

    def test_nobody_edits_a_delivered_order(self):
        self.sign_in('south_manager')
        rug = Order.objects.get(item='Rug')

        answer = self.client.patch(
            f'/api/orders/{rug.pk}/', {'item': 'Carpet'}, content_type='application/json'
        )

        self.assertEqual(answer.status_code, 403)

    def test_a_customer_places_an_order_but_neither_prices_nor_approves_it(self):
        self.sign_in('alice')
        north = Person.objects.get(username='north_manager').branch

        placed = self.client.post(
            '/api/orders/',
            {'branch': north.pk, 'item': 'Clock'},
            content_type='application/json',
        )
        priced = self.client.post(
            '/api/orders/',
            {'branch': north.pk, 'item': 'Cup', 'price': '1.00'},
            content_type='application/json',
        )
        approved = self.client.post(
            '/api/orders/',
            {'branch': north.pk, 'item': 'Vase', 'status': 'approved'},
            content_type='application/json',
        )

        self.assertEqual(placed.status_code, 201, placed.json())
        self.assertEqual(priced.json(), {'price': ['You may not write price.']})
        self.assertEqual(approved.status_code, 400)
        self.assertIn('status', approved.json())

    def test_an_invoice_is_printed_by_whoever_holds_the_action_found_in_the_code(self):
        chair = Order.objects.get(item='Office chair')
        address = f'/api/orders/{chair.pk}/print_invoice/'

        self.sign_in('north_manager')
        self.assertEqual(self.client.post(address).status_code, 200)
        self.sign_in('bob')
        self.assertEqual(self.client.post(address).status_code, 403)
