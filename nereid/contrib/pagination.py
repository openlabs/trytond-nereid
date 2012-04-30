# -*- coding: utf-8 -*-
"""
    __init__

    Pagination helpers

    :copyright: (c) 2012 by Openlabs Technologies & Consulting (P) LTD
    :license: BSD, see LICENSE for more details.
"""
from math import ceil
from werkzeug.utils import cached_property


class BasePagination(object):
    """
    General purpose paginator for doing pagination

    With an empty dataset assert the attributes
    >>> p = Pagination(1, 3, [])
    >>> p.count
    0
    >>> p.pages
    0
    >>> p.begin_count
    0
    >>> p.end_count
    0

    Test with a range(1, 10)
    >>> p = Pagination(1, 3, range(1, 10))
    >>> p.count
    9
    >>> p.all_items()
    [1, 2, 3, 4, 5, 6, 7, 8, 9]
    >>> p.pages
    3
    >>> p.begin_count
    1
    >>> p.end_count
    3

    """

    def __init__(self, page, per_page, data=None):
        """
        :param per_page: Items per page
        :param page: The page to be displayed
        :param data: The data table
        """
        self.per_page = per_page
        self.page = page
        self.data = data if data is not None else []

    @property
    def count(self):
        "Returns the count of data"
        return len(self.data)

    def all_items(self):
        """Returns complete set of items"""
        return self.data

    def items(self):
        """Returns the list of items in current page
        """
        return self.data[self.offset:self.offset + self.per_page]

    def __iter__(self):
        for item in self.items():
            yield item

    def __len__(self):
        return self.count

    @property
    def prev(self):
        """Returns a :class:`Pagination` object for the previous page."""
        return Pagination(self.page - 1, self.per_page, self.data)

    def next(self):
        """Returns a :class:`Pagination` object for the next page."""
        return Pagination(self.page + 1, self.per_page, self.data)

    #: Attributes below this may not require modifications in general cases

    def iter_pages(self, left_edge=2, left_current=2,
                    right_current=2, right_edge=2):
        """Iterates over the page numbers in the pagination.  The four
        parameters control the thresholds how many numbers should be produced
        from the sides.  Skipped page numbers are represented as `None`.
        This is how you could render such a pagination in the templates:

        .. sourcecode:: html+jinja

            {% macro render_pagination(pagination, endpoint) %}
                <div class=pagination>
                {%- for page in pagination.iter_pages() %}
                    {% if page %}
                        {% if page != pagination.page %}
                            <a href="{{ url_for(endpoint, page=page) }}">{{ page }}</a>
                        {% else %}
                            <strong>{{ page }}</strong>
                        {% endif %}
                    {% else %}
                        <span class=ellipsis>…</span>
                    {% endif %}
                {%- endfor %}
                </div>
            {% endmacro %}
        """
        last = 0
        for num in xrange(1, self.pages + 1):
            if num <= left_edge or \
                (num > self.page - left_current - 1 and \
                 num < self.page + right_current) or \
                num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

    offset = property(lambda self: (self.page - 1) * self.per_page)

    prev_num = property(lambda self: self.page - 1)
    has_prev = property(lambda self: self.page > 1)

    next_num = property(lambda self: self.page + 1)
    has_next = property(lambda self: self.page < self.pages)

    pages = property(lambda self: int(ceil(self.count / float(self.per_page))))

    begin_count = property(lambda self: min([
        ((self.page - 1) * self.per_page) + 1, 
        self.count]))
    end_count = property(lambda self: min(
        self.begin_count + self.per_page - 1, self.count))


class Pagination(BasePagination):
    """General purpose paginator for doing pagination which can be used by 
    passing a search domain .Remember that this means the query will be built
    and executed and passed on which could be slower than writing native SQL 
    queries. While this fits into most use cases, if you would like to use
    a SQL query rather than a domain use :class:QueryPagination instead
    """

    # The counting of all possible records can be really expensive if you
    # have too many records and the selectivity of the query is low. For 
    # example -  a query to display all products in a website would be quick
    # in displaying the products but slow in building the navigation. So in 
    # cases where this could be frequent, the value of count may be cached and
    # assigned to this variable
    _count = None

    def __init__(self, obj, domain, page, per_page, order=None):
        """
        :param obj: The object itself. pass self within tryton object
        :param domain: Domain for search in tryton
        :param per_page: Items per page
        :param page: The page to be displayed
        """
        self.obj = obj
        self.domain = domain
        self.order = order
        super(Pagination, self).__init__(page, per_page)

    @cached_property
    def count(self):
        """
        Returns the count of entries
        """
        if self.ids_domain():
            return len(self.domain[0][2])
        if self._count is not None:
            return self._count
        return self.obj.search(domain=self.domain, count=True)

    def all_items(self):
        """Returns complete set of items"""
        if self.ids_domain():
            ids = self.domain[0][2]
        else:
            ids = self.obj.search(self.domain)
        return self.obj.browse(ids)

    def ids_domain(self):
        """Returns True if the domain has only IDs and can skip SQL fetch
        to directly browse the records. Else a False is returned
        """
        return (len(self.domain) == 1) and \
            (self.domain[0][0] == 'id') and \
            (self.domain[0][1] == 'in') and \
            (self.order is None)

    def items(self):
        """Returns the list of browse records of items in the page
        """
        if self.ids_domain():
            ids = self.domain[0][2][self.offset:self.offset + self.per_page]
        else:
            ids = self.obj.search(self.domain, offset=self.offset,
                limit=self.per_page, order=self.order)
        return self.obj.browse(ids)

    @property
    def prev(self, error_out=False):
        """Returns a :class:`Pagination` object for the previous page."""
        return self.obj.paginate(self.page - 1, self.per_page, error_out)

    def next(self, error_out=False):
        """Returns a :class:`Pagination` object for the next page."""
        return self.obj.paginate(self.page + 1, self.per_page, error_out)


class QueryPagination(BasePagination):
    """A fast implementation of pagination which uses a SQL query for 
    generating the IDS and hence the pagination"""

    def __init__(self, obj, search_query, count_query, page, per_page):
        """
        :param search_query: Query to be used for search. It must not include
            an OFFSET or LIMIT as they would be automatically added to the 
            query
        :param count_query: Query to be used to get the count of the pagination
            use a query like `SELECT 1234 AS id` for a query where you do not
            want to manipulate the count
        :param per_page: Items per page
        :param page: The page to be displayed
        """
        self.obj = obj
        self.search_query = search_query
        self.count_query = count_query
        super(QueryPagination, self).__init__(page, per_page)

    @cached_property
    def count(self):
        "Return the count of the Items"
        from trytond.transaction import Transaction
        with Transaction().new_cursor() as transaction:
            transaction.cursor.execute(self.count_query)
            return transaction.cursor.fetchone()[0]

    def all_items(self):
        """Returns complete set of items"""
        from trytond.transaction import Transaction
        with Transaction().new_cursor() as transaction:
            transaction.cursor.execute(self.search_query)
            rv = [x[0] for x in transaction.cursor.fetchall()]
        return self.obj.browse(rv)

    def items(self):
        """Returns the list of browse records of items in the page
        """
        from trytond.transaction import Transaction
        limit_string = ' LIMIT %d' % self.per_page
        offset_string = ' OFFSET %d' % self.offset
        with Transaction().new_cursor() as transaction:
            transaction.cursor.execute(''.join([
                self.search_query, limit_string, offset_string
                ]))
            rv = [x[0] for x in transaction.cursor.fetchall()]
        return self.obj.browse(rv)
