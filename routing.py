# -*- coding: UTF-8 -*-
"""
    nereid.routing

    Routing: Sites, URLs

    :copyright: (c) 2010 by Sharoon Thomas
    :copyright: (c) 2010 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details
"""
from ast import literal_eval

from werkzeug import abort, redirect
from nereid import jsonify, flash, render_template
from nereid.globals import session, request
from trytond.model import ModelView, ModelSQL, fields
from wtforms import Form, TextField, PasswordField, validators


# pylint: disable-msg=E1101
class URLMap(ModelSQL, ModelView):
    """
    URL Map
    ~~~~~~~

    A collection of URLs for a website. This is analogous to werkzeug's
    URL Map.

    :param name: Name of the URL Map
    :param default_subdomain: Default subdomain for URLs in this Map
    :param active: Whether the URL Map is active or not.

    Rules:
    ~~~~~~
    :param rules: O2M URLRules

    Advanced:
    ~~~~~~~~~
    :param charset: default value - utf-8
    :param strict_slashes: Boolean field if / in url map is taken seriously
    :param unique_urls: Enable `redirect_defaults` in the URL Map and
                        redirects the defaults to the URL 
    """
    _name = "nereid.urlmap"
    _description = "Nereid URL Map"

    name = fields.Char(
        'Name', required=True, select=True,
    )
    default_subdomain = fields.Char(
        'Default Subdomain',
    )
    rules = fields.One2Many(
        'nereid.url_rule',
        'url_map',
        'Rules'
    )
    charset = fields.Char('Char Set')
    strict_slashes = fields.Boolean('Strict Slashes')
    unique_urls = fields.Boolean('Unique URLs')
    active = fields.Boolean('Active')

    def default_active(self):
        "By default URL is active"
        return True

    def default_charset(self):
        "By default characterset is utf-8"
        return 'utf-8'

    def get_rules_arguments(self, map_id):
        """
        Constructs a list of dictionary of arguments needed
        for URL Rule construction. A wrapper around the 
            URL RULE get_rule_arguments
        """
        rule_args = [ ]
        rule_obj = self.pool.get('nereid.url_rule')
        url_map = self.browse(map_id)
        for rule in url_map.rules:
            rule_args.append(
                rule_obj.get_rule_arguments(rule.id)
            )
        return rule_args

URLMap()


class LoginForm(Form):
    "Default Login Form"
    email = TextField('e-mail', [validators.Required(), validators.Email()])
    password = PasswordField('Password', [validators.Required()])


class WebSite(ModelSQL, ModelView):
    """
    Web Site
    ~~~~~~~~

    One of the most powerful features of Nereid is the ability to 
    manage multiple websites from one back-end. A web site in nereid 
    represents a collection or URLs, settings.

    :param name: Name of the web site
    :param base_url: The unique URL of the website, You cannot have two
                     websites, with the same base_url
    :param url_map: The active URL Map for the website (M2O URLMap)
    :param company: The company linked with the website.
    :param active: Whether the website is active or not.

    """
    _name = "nereid.website"
    _description = "Nereid WebSite"

    #: The name field is used for both information and also as
    #: the site identifier for nereid. The WSGI application requires
    #: SITE argument. The SITE argument is then used to load URLs and
    #: other settings for the website. Needs to be unique
    name = fields.Char('Name', required=True, select=True)

    #: The URLMap is made as a different object which functions as a 
    #: collection of Rules. This will allow easy replication of sites
    #: which perform with same URL structures but different templates
    url_map = fields.Many2One('nereid.urlmap', 'URL Map', required=True)

    #: The company to which the website belongs. Useful when creating
    #: records like sale order which require a company to be present
    company = fields.Many2One('company.company', 'Company', required=True)

    active = fields.Boolean('Active')

    #: The list of countries this website operates in. Used for generating
    #: Countries list in the registration form etc.
    countries = fields.Many2Many(
        'nereid.website-country.country', 'website', 'country',
        'Countries Available')

    def default_active(self):
        return True

    def __init__(self):
        super(WebSite, self).__init__()
        self._sql_constraints = [
            ('name_uniq', 'UNIQUE(name)',
             'Another site with the same name already exists!')
        ]

    def country_list(self):
        """
        Return the list of countries in JSON
        """
        return jsonify([
            {'key': c.id, 'value': c.name} \
                for c in request.nereid_website.countries
            ])

    def subdivision_list(self):
        """
        Return the list of states for given country
        """
        country = int(request.args.get('country', 0))
        if country not in [c.id for c in request.nereid_website.countries]:
            abort(404)

        subdivision_obj = self.pool.get('country.subdivision')
        ids = subdivision_obj.search([('country', '=', country)])
        subdivisions = subdivision_obj.browse(ids)
        return jsonify(
            result = [{'key': s.id, 'value': s.name} for s in subdivisions]
            )

    def get_urls(self, name):
        """
        Return complete list of URLs
        """
        urlmap_obj = self.pool.get('nereid.urlmap')
        website_id = self.search([('name', '=', name)])
        if not website_id:
            raise RuntimeError("Website with Name %s not found" % name)

        website = self.browse(website_id[0])
        return urlmap_obj.get_rules_arguments(website.url_map.id)

    def stats(self, **arguments):
        """
        Test method.
        """
        return u'Request: %s\nArguments: %s\nEnviron: %s\n' \
            % (request, arguments, request.environ)

    def home(self):
        """
        A sample home method
        """
        return u'''Welcome to Nereid
This is the default home page and needs replacing. To build
your own home method, inherit the model nereid.website and implement
the `home` method to replace this function.
        '''

    def login(self):
        """
        Simple login based on the email and password

        Required post data see :class:LoginForm
        """
        login_form = LoginForm(request.form)

        if request.method == 'POST' and login_form.validate():
            address_obj = self.pool.get('party.address')
            result = address_obj.authenticate(
                login_form.email.data, login_form.password.data)
            if result is None:
                flash("Invalid login credentials")
            else:
                flash("You are now logged in. Welcome %s" % result.name)
                session['user'] = result.id
                return redirect(request.args.get('next', '/'))
        return render_template('login.jinja', login_form=login_form)

    def logout(self):
        "Log the user out"
        session.pop('user', None)
        flash('You have been logged out successfully. Thanks for visiting us')
        return redirect(request.args.get('next', '/'))

    def registration(self):
        register_form = RegistrationForm(request.form)
        register_form.country.choices = [
            (c.id, c.name) for c in request.nereid_website.countries
            ]
        if request.method == 'POST' and register_form.validate():
            address_obj = self.pool.get('party.address')
            contact_mech_obj = self.pool.get('party.contact_mechanism')
            party_obj = self.pool.get('party.party')
            opportunity_obj = self.pool.get('sale.opportunity')

            registration_data = register_form.data

            # First search if an address with the email already exists
            existing = contact_mech_obj.search([
                ('value', '=', registration_data['email']),
                ('type', '=', 'email')])
            if existing:
                flash('A registration already exists with this email. '
                    'Please contact customer care')
            else:
                # Create Party
                party_id = party_obj.create({
                    'name': registration_data['company'],
                    'addresses': [
                        ('create', {
                            'name': registration_data['name'],
                            'street': registration_data['street'],
                            'streetbis': registration_data['streetbis'],
                            'zip': registration_data['zip'],
                            'city': registration_data['city'],
                            'country': registration_data['country'],
                            'subdivision': registration_data['subdivision'],
                            })],
                    })
                party = party_obj.browse(party_id)

                # Create email as contact mech and assign as email
                contact_mech_id = contact_mech_obj.create({
                        'type': 'email',
                        'party': party.id,
                        'email': registration_data['email'],
                    })
                address_obj.write(party.addresses[0].id, 
                    {'email': contact_mech_id})

                # Finally create opportunity
                opportunity = opportunity_obj.create({
                    'party': party.id,
                    'address': party.addresses[0].id,
                    'company': request.nereid_website.company.id,
                    'description': 'New Registration',
                    'comment': registration_data['comments'],
                    'employee': request.nereid_website.default_employee.id
                    })

                flash('''Your registration has been completed successfully
                Our customer care will soon be in touch with you.
                Your registration number is: %s''' % opportunity)
                return redirect(request.args.get('next', '/'))
        return render_template('registration.jinja', form=register_form)    
        
    def registration(self):
        register_form = RegistrationForm(request.form)
        register_form.country.choices = [
            (c.id, c.name) for c in request.nereid_website.countries
            ]

        if request.method == 'POST' and register_form.validate():
            address_obj = self.pool.get('party.address')
            contact_mech_obj = self.pool.get('party.contact_mechanism')
            party_obj = self.pool.get('party.party')

            registration_data = register_form.data

            # First search if an address with the email already exists
            existing = contact_mech_obj.search([
                ('value', '=', registration_data['email']),
                ('type', '=', 'email')])
            if existing:
                flash('A registration already exists with this email. '
                    'Please contact customer care')
            else:
                # Create Party
                party_id = party_obj.create({
                    'name': registration_data['company'],
                    'addresses': [
                        ('create', {
                            'name': registration_data['name'],
                            'street': registration_data['street'],
                            'streetbis': registration_data['streetbis'],
                            'zip': registration_data['zip'],
                            'city': registration_data['city'],
                            'country': registration_data['country'],
                            'subdivision': registration_data['subdivision'],
                            })],
                    })
                party = party_obj.browse(party_id)

                # Create email as contact mech and assign as email
                contact_mech_id = contact_mech_obj.create({
                        'type': 'email',
                        'party': party.id,
                        'email': registration_data['email'],
                    })
                address_obj.write(party.addresses[0].id, 
                    {'email': contact_mech_id})

                flash('''Your registration has been completed successfully
                Our customer care will soon be in touch with you.''')
                return redirect(request.args.get('next', '/'))
        return render_template('registration.jinja', form=register_form)

WebSite()


class URLRule(ModelSQL, ModelView):
    """
    URL Rule
    ~~~~~~~~

    A rule that represents a single URL pattern

    :param path: Path of the URL
    :param name: Name of the URL. This is used for reverse mapping, hence
                 needs to be unique
    :param handler: The handler of this URL or the target model.method
                     which is called. The representation is::

        <model>.<method>

    For example: To call list_parties method in party.party use:

        party.party.list_parties

    The signature of the method being called should be:

        def method(self, **arguments):
            return "Hello World"

    where request is the request object and arguments is the dictionary
    of the values generated from the match of the URL

    :param active: Whether the website is active or not.

    Advanced
    ~~~~~~~~~

    :param defaults: Defaults of the URL (O2M - URLRuleDefaults)

    :param method: POST, GET, 
    :param only_for_generation: URL will not be mapped, but can be used 
            for URL generation. Example for static pages, where content
            delivery is managed by apache, but URL generation is necessary
    :param redirect_to: (M2O self) Another URL to which the redirect has to
            be done
    :param sequence: Numeric sequence of the URL Map.
    :param url_map: Relation field for url_rule o2m
    """
    _name = "nereid.url_rule"
    _description = "Nereid URL Rule"
    _rec_name = 'rule'

    rule = fields.Char('Rule', required=True, select=True,)
    endpoint = fields.Char('Endpoint', required=True, select=True,)
    active = fields.Boolean('Active')
    defaults = fields.One2Many('nereid.url_rule_defaults', 'rule', 'Defaults')
    methods = fields.Selection(
        [
            ('("POST",)', 'POST'),
            ('("GET",)', 'GET'),
            ('("GET", "POST")', 'GET/POST')
        ],
        'Methods', required=True)
    only_for_genaration = fields.Boolean('Only for Generation')
    redirect_to = fields.Char('Redirect To')
    sequence = fields.Integer('Sequence', required=True,)
    url_map = fields.Many2One('nereid.urlmap', 'URL Map')

    def __init__(self):
        super(URLRule, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def default_active(self):
        return True

    def default_methods(self):
        return '("GET",)'

    def get_rule_arguments(self, rule_id):
        """
        Return the arguments of a Rule in the corresponding format
        """
        rule = self.browse(rule_id)
        defaults = dict(
            [(i.key, i.value) for i in rule.defaults]
        )
        return {
                'rule': rule.rule,
                'endpoint': rule.endpoint,
                'methods': rule.methods and literal_eval(rule.methods) or None,
                'build_only': rule.only_for_genaration,
                'defaults': defaults,
                'redirect_to': rule.redirect_to or None,
            }

URLRule()


class URLRuleDefaults(ModelSQL, ModelView):
    """
    Defaults for the URL

    :param key: The char for the default's key
    :param value: The Value for the default's Value
    :param Rule: M2O Rule
    """
    _name = "nereid.url_rule_defaults"
    _description = "Nereid URL Rule Defaults"
    _rec_name = 'key'

    key = fields.Char('Key', required=True, select=True)
    value = fields.Char('Value', required=True, select=True)
    rule = fields.Many2One('nereid.url_rule', 'Rule', required=True, 
        select=True)

URLRuleDefaults()


class WebsiteCountry(ModelSQL):
    "Website Country Relations"
    _name = 'nereid.website-country.country'
    _description = __doc__

    website = fields.Many2One('nereid.website', 'Website')
    country = fields.Many2One('country.country', 'Country')

WebsiteCountry()
