# -*- coding: UTF-8 -*-
'''
    nereid.wrappers

    Implements the WSGI wrappers

    :copyright: (c) 2010-2012 by Openlabs Technologies & Consulting (P) Ltd.
    :license: BSD, see LICENSE for more details
'''
from werkzeug.utils import cached_property
from flask.wrappers import Request as RequestBase, Response as ResponseBase
from flask.helpers import flash
import ccy
from .globals import current_app, session


def _get_website_name(host):
    """The host could have the host_name and port number. This will try
    to get the best possible guess of the website name from the host name
    """
    #XXX: Needs improvement
    return host.split(':')[0]


class Request(RequestBase):
    "Request Object"

    @cached_property
    def nereid_website(self):
        """Fetch the Browse Record of current website."""
        website_obj = current_app.pool.get('nereid.website')
        website, = website_obj.search([
            ('name', '=', _get_website_name(self.host))]
        )
        return website_obj.browse(website)

    @cached_property
    def nereid_user(self):
        """Fetch the browse record of current user or None."""
        user_obj = current_app.pool.get('nereid.user')
        if 'user' not in session:
            return user_obj.browse(self.nereid_website.guest_user.id)
        return user_obj.browse(session['user'])

    @cached_property
    def nereid_currency(self):
        """Return a browse record for the currency."""
        currency_code = ccy.countryccy(self.nereid_language.code[-2:])
        for currency in self.nereid_website.currencies:
            if currency.code == currency_code:
                return currency
        raise RuntimeError("Currency %s is not valid" % currency_code)

    @cached_property
    def nereid_language(self):
        """Return a browse record for the language."""
        from trytond.transaction import Transaction
        lang_obj = current_app.pool.get('ir.lang')
        lang_ids = lang_obj.search([('code', '=', Transaction().language)])
        if not lang_ids:
            flash("We are sorry we don't speak your language yet!")
            lang_ids = [self.nereid_website.default_language.id]
        return lang_obj.browse(lang_ids[0])

    @cached_property
    def is_guest_user(self):
        """Return true if the user is guest."""
        return ('user' not in session)


class Response(ResponseBase):
    pass
