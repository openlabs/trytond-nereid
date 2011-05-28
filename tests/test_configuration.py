# -*- coding: utf-8 -*-
"""
    nereid.test

    Test the configuration features for nereid

    :copyright: (c) 2010-2011 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details.
"""
import json
from ast import literal_eval
from decimal import Decimal
import unittest2 as unittest

from minimock import Mock
import smtplib
smtplib.SMTP = Mock('smtplib.SMTP')
smtplib.SMTP.mock_returns = Mock('smtp_connection')

from trytond.config import CONFIG
CONFIG.options['db_type'] = 'sqlite'
CONFIG.options['data_path'] = '/tmp/temp_tryton_data/'
CONFIG['smtp_server'] = 'smtp.gmail.com'
CONFIG['smtp_user'] = 'test@xyz.com'
CONFIG['smtp_password'] = 'testpassword'
CONFIG['smtp_port'] = 587
CONFIG['smtp_tls'] = True
from trytond.modules import register_classes
register_classes()

from nereid.testing import testing_proxy
from trytond.transaction import Transaction

GUEST_EMAIL = 'guest@example.com'
NEW_USER = 'new@example.com'
NEW_PASS = 'password'

class TestNereidConfiguration(unittest.TestCase):
    'Test case for nereid configuration'

    @classmethod
    def setUpClass(cls):
        # Install module
        testing_proxy.install_module('nereid')

        country_obj = testing_proxy.pool.get('country.country')
        address_obj = testing_proxy.pool.get('party.address')

        with Transaction().start(testing_proxy.db_name, 1, None) as txn:
            # Create company
            company = testing_proxy.create_company('Test Company')
            testing_proxy.set_company_for_user(1, company)

            cls.guest_user = testing_proxy.create_guest_user(email=GUEST_EMAIL)
            
            cls.regd_user_id = testing_proxy.create_user_party('Registered User', 
                'email@example.com', 'password')

            cls.available_countries = country_obj.search([], limit=5)
            cls.site = testing_proxy.create_site('testsite.com', 
                countries = [('set', cls.available_countries)])

            testing_proxy.create_template('home.jinja', ' Home ', cls.site)
            testing_proxy.create_template(
                'login.jinja', 
                '{{ login_form.errors }} {{get_flashed_messages()}}', cls.site)
            testing_proxy.create_template(
                'registration.jinja', 
                '{{ form.errors }} {{get_flashed_messages()}}', cls.site)
            
            testing_proxy.create_template(
                'reset-password.jinja', '', cls.site)
            testing_proxy.create_template(
                'change-password.jinja',
                '{{ change_password_form.errors }}', cls.site)
            testing_proxy.create_template(
                'address-edit.jinja',
                '{{ form.errors }}', cls.site)
            testing_proxy.create_template(
                'address.jinja', '', cls.site)
            testing_proxy.create_template(
                'account.jinja', '', cls.site)

            txn.cursor.commit()

    def get_app(self, **options):
        options.update({
            'SITE': 'testsite.com',
            'GUEST_USER': self.guest_user,
            })
        return testing_proxy.make_app(**options)
        
    def setUp(self):
        self.address_obj = testing_proxy.pool.get('party.address')
        self.country_obj = testing_proxy.pool.get('country.country')
        self.subdivision_obj = testing_proxy.pool.get('country.subdivision')
        self.website_obj = testing_proxy.pool.get('nereid.website')
        self.contact_mech_obj = testing_proxy.pool.get('party.contact_mechanism')
        
    def test_0010_registration_form(self):
        "Successful rendering of an empty registration page"
        app = self.get_app()
        with app.test_client() as c:
            response = c.get('/en_US/registration')
            self.assertEqual(response.status_code, 200)

    def test_0020_registration(self):
        "Successful registration of a user"
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            website_id = self.website_obj.search([])[0]
            website = self.website_obj.browse(website_id)
            country = website.countries[0]
            subdivision = country.subdivisions[0]
            
        app = self.get_app()
        with app.test_client() as c:
            # Rendering of empty registration page
            response = c.get('/en_US/registration')
            self.assertEqual(response.status_code, 200)

            # Missing some information in filling the form 
            # should return registration form back.
            registration_data = {
                'name': 'New Test user',
                #'company': 'Test Company',
                'street': 'New Street',
                'email': NEW_USER,
                'password': NEW_PASS,
            }

            response = c.post('/en_US/registration', data=registration_data)
            self.assertEqual(response.status_code, 200)

            # Filling all required values in the registration form 
            # should redirect to home page.
            registration_data.update({
                'zip': 'ABC123',
                'city': 'Test City',
                'country': country.id,
                'subdivision': subdivision.id,
                'email': NEW_USER,
                'confirm': NEW_PASS,
            })

            response = c.post('/en_US/registration', data=registration_data)
            self.assertEqual(response.status_code, 302)
            # Checking whether new has been created.
            # An active user will have activation_code = False
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user_email = self.contact_mech_obj.search([
                ('type', '=', 'email'), 
                ('value', '=', NEW_USER)])[0]
            new_user_id, = self.address_obj.search(
                [('email', '=', new_user_email)])
            new_user = self.address_obj.browse(new_user_id)
            self.assertEqual(new_user.email.value, NEW_USER)
            self.assertTrue(new_user.activation_code != False)

    def test_0030_activation(self):
        "Activation of user account"
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user_email = self.contact_mech_obj.search([
                ('type', '=', 'email'), 
                ('value', '=', NEW_USER)])[0]
            new_user_id, = self.address_obj.search(
                [('email', '=', new_user_email)])
            new_user = self.address_obj.browse(new_user_id)
        app = self.get_app()
        with app.test_client() as c:
            # Try logging in without activating the code        
            response = c.post('/en_US/login', 
                data={'email': u'new@example.com', 'password': u'password'})
            self.assertEqual(response.status_code, 200)
            
            # For account activation a link is send as email which is in 
            # format below, clicking on it will activate the account and 
            # set activation_code=False 
            response = c.get('/en_US/activate-account/%s/%s' % (new_user.id, 
                new_user.activation_code))
            self.assertEqual(response.status_code, 302)
            
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user = self.address_obj.browse(new_user_id)
            self.assertFalse(new_user.activation_code)

        with app.test_client() as c:
            response = c.post('/en_US/login', 
                data={'email': u'new@example.com', 'password': u'password'})
            self.assertEqual(response.status_code, 302)

    def test_0040_change_password(self):
        "Change of password"
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})
            response = c.get('/en_US/change-password')
            self.assertEqual(response.status_code, 200)

            response = c.post('/en_US/change-password', data={
                'password': 'new-password',
                'confirm': 'password'
            })
            self.assertEqual(response.status_code, 200)

            response = c.post('/en_US/change-password', data={
                'password': 'new-password',
                'confirm': 'new-password'
            })
            self.assertEqual(response.status_code, 302)

    def test_0050_reset_account(self):
        "Reset the password of a user"
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user_id, = self.address_obj.search([('email', '=', NEW_USER)])
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'new-password'})
            response = c.get('/en_US/reset-account')
            self.assertEqual(response.status_code, 200)

            response = c.post('/en_US/reset-account', data={
                'email': 'new@example.com',
            })
            self.assertEqual(response.status_code, 302)
            
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user = self.address_obj.browse(new_user_id)
            self.assertTrue(new_user.activation_code != False)

        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'new-password'})
            response = c.post('/en_US/change-password', data={
                'password': 'password',
                'confirm': 'password'
            })
            self.assertEqual(response.status_code, 302)
            
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user = self.address_obj.browse(new_user_id)
            self.assertTrue(new_user.activation_code != False)

        with app.test_client() as c:
            c.get('/en_US/logout')
            response = c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'new-password'})
            self.assertEqual(response.status_code, 200)
            response = c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})
            self.assertEqual(response.status_code, 302)

    def test_0060_edit_address(self):
        "Edit the address of a user"
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            new_user_email = self.contact_mech_obj.search([
                ('type', '=', 'email'), 
                ('value', '=', NEW_USER)])[0]
            new_user_id, = self.address_obj.search(
                [('email', '=', new_user_email)])
            new_user = self.address_obj.browse(new_user_id)
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})

            # On submitting an empty form the page should load back
            response = c.get('/en_US/edit-address/%d' % new_user.id)
            self.assertEqual(response.status_code, 200)

            # On submitting url with id the address must change
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            website_id = self.website_obj.search([])[0]
            website = self.website_obj.browse(website_id)
            country = website.countries[1]
            subdivision = country.subdivisions[2]
            address_data = {
                'name': 'New test User 2',
                'street': 'New Street 2',
                'street2': 'New Street2 2',
                'zip': '678GHB',
                'city': 'Test City 2',
                'country': country.id,
                'subdivision': subdivision.id,
                'email': new_user_email,
                }
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})
            response = c.post('/en_US/edit-address/%d' % new_user.id,
                data=address_data)
            self.assertEqual(response.status_code, 302)

            # On submitting url withour correct id, new address 
            # should be created
            address_data = {
                'name': 'New test User 3',
                'street': 'New Street 3',
                'street2': 'New Street2 3',
                'zip': '678HHH',
                'city': 'Test City 3',
                'country': country.id,
                'subdivision': subdivision.id,
                'email': new_user_email,
                }
            response = c.post('/en_US/edit-address/%d' % 0, data=address_data)
            self.assertEqual(response.status_code, 302)
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            self.assertEqual(len(new_user.party.addresses), 2)

    def test_0070_view_address(self):
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})
            response = c.get('/en_US/view-address')
            self.assertEqual(response.status_code, 200)

    def test_0080_login(self):
        "Check whether a registered user can login"
        app = self.get_app()
        with app.test_client() as c:

            # Correct entries will redirect to home or some other page
            response = c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})
            self.assertEqual(response.status_code, 302)

            # Wrong entries will render the login page again
            response = c.post('/en_US/login', 
                data={
                    'email': 'new@example.com', 
                    'password': 'wrong-password'})
            self.assertEqual(response.status_code, 200)

    def test_0090_logout(self):
        "Check whether a logged in user can logout"
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})

            response = c.get('/en_US/logout')
            self.assertEqual(response.status_code, 302)

    def test_0100_account(self):
        "Check the display the account details of a user"
        app = self.get_app()
        with app.test_client() as c:
            c.post('/en_US/login', 
                data={'email': 'new@example.com', 'password': 'password'})

            response = c.get('/en_US/account')
            self.assertEqual(response.status_code, 200)

    def test_0110_country_list(self):
        "Check if the website countries are there in country list"
        app = self.get_app()
        with app.test_client() as c:
            response = c.get('/en_US/countries')
            self.assertEqual(len(eval(response.data)['result']), 5)

    def test_0120_subdivision_list(self):
        "Check if a country has states"
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            website_id = self.website_obj.search([])[0]
            website = self.website_obj.browse(website_id)
            country = website.countries[1]
            subdivision = country.subdivisions[2]
        app = self.get_app()
        with app.test_client() as c:
            response = c.get('/en_US/subdivisions?country=%d' % country)
            self.assertEqual(not(len(eval(response.data)['result'])), 0)
            
    def test_0130_addtional_details(self):
        "Test whether the additional details work"
        address_additional = testing_proxy.pool.get('address.additional_details')
        with Transaction().start(testing_proxy.db_name, testing_proxy.user, None):
            any_user_id = self.address_obj.search([])[0]
            additional_id = address_additional.create({
                'type': 'dob',
                'value': '1/1/2000',
                'sequence': 10,
                'address': any_user_id})
            any_user = self.address_obj.browse(any_user_id)
            self.assertEqual(any_user.additional_details[0].value, '1/1/2000')
            

def suite():
    "Nereid test suite"
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestNereidConfiguration)
        )
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
