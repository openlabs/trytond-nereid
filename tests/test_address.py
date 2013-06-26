# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import json
import unittest

import pycountry
from mock import patch
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction
from trytond.config import CONFIG
from nereid.testing import NereidTestCase

CONFIG['smtp_server'] = 'smtpserver'
CONFIG['smtp_user'] = 'test@xyz.com'
CONFIG['smtp_password'] = 'testpassword'
CONFIG['smtp_port'] = 587
CONFIG['smtp_tls'] = True
CONFIG['smtp_from'] = 'from@xyz.com'


class TestAddress(NereidTestCase):
    'Test Address'

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid')

        self.nereid_website_obj = POOL.get('nereid.website')
        self.nereid_user_obj = POOL.get('nereid.user')
        self.url_map_obj = POOL.get('nereid.url_map')
        self.company_obj = POOL.get('company.company')
        self.currency_obj = POOL.get('currency.currency')
        self.language_obj = POOL.get('ir.lang')
        self.country_obj = POOL.get('country.country')
        self.subdivision_obj = POOL.get('country.subdivision')
        self.party_obj = POOL.get('party.party')
        self.address_obj = POOL.get('party.address')
        self.contact_mech_obj = POOL.get('party.contact_mechanism')

        self.templates = {
            'home.jinja': '{{get_flashed_messages()}}',
            'login.jinja':
                    '{{ login_form.errors }} {{get_flashed_messages()}}',
            'registration.jinja':
                    '{{ form.errors }} {{get_flashed_messages()}}',
            'reset-password.jinja': '',
            'change-password.jinja':
                    '{{ change_password_form.errors }}',
            'address-edit.jinja':
                'Address Edit {% if address %}ID:{{ address.id }}{% endif %}'
                '{{ form.errors }}',
            'address.jinja': '',
            'account.jinja': '',
            'emails/activation-text.jinja': 'activation-email-text',
            'emails/activation-html.jinja': 'activation-email-html',
            'emails/reset-text.jinja': 'reset-email-text',
            'emails/reset-html.jinja': 'reset-email-html',
        }

        # Patch SMTP Lib
        self.smtplib_patcher = patch('smtplib.SMTP')
        self.PatchedSMTP = self.smtplib_patcher.start()

    def tearDown(self):
        # Unpatch SMTP Lib
        self.smtplib_patcher.stop()

    def create_countries(self, count=5):
        """
        Create some sample countries and subdivisions
        """
        for country in list(pycountry.countries)[0:count]:
            country_id, = self.country_obj.create([{
                'name': country.name,
                'code': country.alpha2,
            }])
            try:
                divisions = pycountry.subdivisions.get(
                    country_code=country.alpha2
                )
            except KeyError:
                pass
            else:
                self.subdivision_obj.create([{
                    'country': country_id,
                    'name': subdivision.name,
                    'code': subdivision.code,
                    'type': subdivision.type.lower(),
                } for subdivision in list(divisions)[0:count]])

    def setup_defaults(self):
        """
        Setup the defaults
        """
        usd, = self.currency_obj.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])
        self.party, = self.party_obj.create([{
            'name': 'Openlabs',
        }])
        self.company, = self.company_obj.create([{
            'party': self.party,
            'currency': usd,
        }])
        self.guest_party, = self.party_obj.create([{
            'name': 'Guest User',
        }])
        self.guest_user, = self.nereid_user_obj.create([{
            'party': self.guest_party,
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': self.company.id,
        }])
        party, = self.party_obj.create([{
            'name': 'Registered User',
        }])
        self.registered_user, = self.nereid_user_obj.create([{
            'party': party,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': self.company,
        }])

        self.create_countries()
        self.available_countries = self.country_obj.search([], limit=5)

        url_map_id, = self.url_map_obj.search([], limit=1)
        en_us, = self.language_obj.search([('code', '=', 'en_US')])
        self.nereid_website_obj.create([{
            'name': 'localhost',
            'url_map': url_map_id,
            'company': self.company,
            'application_user': USER,
            'default_language': en_us,
            'guest_user': self.guest_user,
            'countries': [('set', self.available_countries)],
        }])

    def get_template_source(self, name):
        """
        Return templates
        """
        return self.templates.get(name)

    def test_0010_add_address(self):
        """
        Add an address for the user
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            registered_user = self.registered_user

            address_data = {
                'name': 'Name',
                'street': 'Street',
                'streetbis': 'StreetBis',
                'zip': 'zip',
                'city': 'City',
                'email': 'email@example.com',
                'phone': '1234567890',
                'country': self.available_countries[0].id,
                'subdivision': self.country_obj(
                            self.available_countries[0]
                        ).subdivisions[0].id,
            }

            with app.test_client() as c:
                response = c.post(
                    '/en_US/login',
                    data={
                        'email': 'email@example.com',
                        'password': 'password',
                    }
                )
                self.assertEqual(response.status_code, 302) # Login success

                # Assert that the user has only 1 address, which gets created
                # automatically with the party
                self.assertEqual(len(registered_user.party.addresses), 1)
                existing_address, = registered_user.party.addresses

                # POST and a new address must be created
                response = c.post('/en_US/save-new-address', data=address_data)
                self.assertEqual(response.status_code, 302)

                # Re browse the record
                registered_user = self.nereid_user_obj(
                    self.registered_user.id
                )
                # Check if the user has two addresses now
                self.assertEqual(len(registered_user.party.addresses), 2)
                for address in registered_user.party.addresses:
                    if address != existing_address:
                        break
                else:
                    self.fail("New address not found")

                self.assertEqual(address.name, address_data['name'])
                self.assertEqual(address.street, address_data['street'])
                self.assertEqual(address.streetbis, address_data['streetbis'])
                self.assertEqual(address.zip, address_data['zip'])
                self.assertEqual(address.city, address_data['city'])
                self.assertEqual(address.email, address_data['email'])
                self.assertEqual(address.phone, address_data['phone'])
                self.assertEqual(address.country.id, address_data['country'])
                self.assertEqual(
                    address.subdivision.id, address_data['subdivision']
                )

    def test_0020_edit_address(self):
        """
        Edit an address for the user
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            registered_user = self.registered_user
            address_data = {
                'name': 'Name',
                'street': 'Street',
                'streetbis': 'StreetBis',
                'zip': 'zip',
                'city': 'City',
                'email': 'email@example.com',
                'phone': '1234567890',
                'country': self.available_countries[0].id,
                'subdivision': self.country_obj(
                        self.available_countries[0]).subdivisions[0].id,
            }

            with app.test_client() as c:
                response = c.post(
                    '/en_US/login',
                    data={
                        'email': 'email@example.com',
                        'password': 'password',
                    }
                )
                self.assertEqual(response.status_code, 302) # Login success

                # Assert that the user has only 1 address, which gets created
                # automatically with the party
                self.assertEqual(len(registered_user.party.addresses), 1)
                existing_address, = registered_user.party.addresses

                response = c.get(
                    '/en_US/edit-address/%d' % existing_address.id
                )
                self.assertTrue('ID:%s' % existing_address.id in response.data)

                # POST to the existing address must updatethe existing address
                response = c.post(
                    '/en_US/edit-address/%d' % existing_address.id,
                    data=address_data
                )
                self.assertEqual(response.status_code, 302)

                # Assert that the user has only 1 address, which gets created
                # automatically with the party
                self.assertEqual(len(registered_user.party.addresses), 1)

                address = self.address_obj(existing_address.id)
                self.assertEqual(address.name, address_data['name'])
                self.assertEqual(address.street, address_data['street'])
                self.assertEqual(address.streetbis, address_data['streetbis'])
                self.assertEqual(address.zip, address_data['zip'])
                self.assertEqual(address.city, address_data['city'])
                self.assertEqual(address.email, address_data['email'])
                self.assertEqual(address.phone, address_data['phone'])
                self.assertEqual(address.country.id, address_data['country'])
                self.assertEqual(
                    address.subdivision.id, address_data['subdivision']
                )

    def test_0030_view_addresses(self):
        """
        Display a list of all addresses
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            with app.test_client() as c:
                response = c.post(
                    '/en_US/login',
                    data={
                        'email': 'email@example.com',
                        'password': 'password',
                    }
                )
                self.assertEqual(response.status_code, 302) # Login success

            with app.test_client() as c:
                response = c.get('/en_US/view-address')
                self.assertEqual(response.status_code, 302) # Redir to login

    def test_0040_country_list(self):
        """
        Check if the website countries are there in country list
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/en_US/countries')
                self.assertEqual(response.status_code, 200) # Login success
                self.assertEqual(len(json.loads(response.data)['result']), 5)

    def test_0050_subdivision_list(self):
        """
        Check if a country's subdivisions are returned
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            # Set in :meth:`setup_defaults`
            country = self.available_countries[1]

            with app.test_client() as c:
                response = c.get('/en_US/subdivisions?country=%d' % country)
                self.assertNotEqual(
                    len(json.loads(response.data)['result']), 0
                )


def suite():
    "Nereid test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestAddress)
        )
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
