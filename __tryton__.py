# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

{
    'name': 'Nereid',
    'version': '1.8.0.1',
    'author': 'Openlabs Technologies & Consulting',
    'email': 'info@openlabs.co.in',
    'website': 'http://www.openlabs.co.in/',
    'description': '''Base configuration of Nereid:

    1. Routing: Sites, URL Maps
    ''',
    'depends': [
        'ir',
        'res',
        'company',
        'electronic_mail_template',
    ],
    'xml': [
       'defaults.xml',
       'configuration.xml',
       'static_file.xml'
    ],
    'translation': [
    ],
}

