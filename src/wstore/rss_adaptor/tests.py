
from django.test import TestCase

from wstore.rss_adaptor import rssAdaptor


class FakeUrlib2Rss():

    _opener = None

    def __init__(self):
        self._opener = self.Opener(self.Response())

    def build_opener(self):
        return self._opener

    class Opener():

        _response = None
        _method = None
        _header = None
        _body = None
        _url = None

        def __init__(self, response):
            self._response = response

        def open(self, request):
            self._method = request.get_method()
            self._header = request.get_header('Content-type')
            self._body = request.data
            self._url = request.get_full_url()

            return self._response

    class Response():
        url = 'http://response.com/'
        code = 201


class RSSAdaptorTestCase(TestCase):

    def test_rss_client(self):

        expected_xml = """
        <cdrs>
            <cdr>
                <id_service_provider>test_provider</id_service_provider> 
                <id_application>test_service</id_application> 
                <id_event>Subscription event</id_event> 
                <id_correlation>2</id_correlation> 
                <purchase_code>1234567890</purchase_code> 
                <parent_app_id>test_offering</parent_app_id> 
                <product_class>SaaS</product_class> 
                <description>The description</description> 
                <cost_currency>EUR</cost_currency> 
                <cost_units>10</cost_units> 
                <tax_currency>EUR</tax_currency> 
                <tax_units>0.0</tax_units> 
                <cdr_source>WStore</cdr_source> 
                <id_operator>1</id_operator> 
                <id_country>SP</id_country> 
                <time_stamp>10-05-13 10:00:00</time_stamp> 
                <id_user>test_customer</id_user> 
            </cdr>
            <cdr>
                <id_service_provider>test_provider</id_service_provider> 
                <id_application>test_service</id_application> 
                <id_event>Pay per use event</id_event> 
                <id_correlation>3</id_correlation> 
                <purchase_code>1234567890</purchase_code> 
                <parent_app_id>test_offering</parent_app_id> 
                <product_class>SaaS</product_class> 
                <description>The description</description> 
                <cost_currency>EUR</cost_currency> 
                <cost_units>1</cost_units> 
                <tax_currency>EUR</tax_currency> 
                <tax_units>0.0</tax_units> 
                <cdr_source>WStore</cdr_source> 
                <id_operator>1</id_operator> 
                <id_country>SP</id_country> 
                <time_stamp>10-05-13 10:00:00</time_stamp> 
                <id_user>test_customer</id_user> 
            </cdr>
        </cdrs>"""

        cdr = [{
            'provider': 'test_provider',
            'service': 'test_service',
            'defined_model': 'Subscription event',
            'correlation': '2',
            'purchase': '1234567890',
            'offering': 'test_offering',
            'product_class': 'SaaS',
            'description': 'The description',
            'cost_currency': 'EUR',
            'cost_value': '10',
            'tax_currency': 'EUR',
            'tax_value': '0.0',
            'source': 'WStore',
            'operator': '1',
            'country': 'SP',
            'time_stamp': '10-05-13 10:00:00',
            'customer': 'test_customer',
        },
        {
            'provider': 'test_provider',
            'service': 'test_service',
            'defined_model': 'Pay per use event',
            'correlation': '3',
            'purchase': '1234567890',
            'offering': 'test_offering',
            'product_class': 'SaaS',
            'description': 'The description',
            'cost_currency': 'EUR',
            'cost_value': '1',
            'tax_currency': 'EUR',
            'tax_value': '0.0',
            'source': 'WStore',
            'operator': '1',
            'country': 'SP',
            'time_stamp': '10-05-13 10:00:00',
            'customer': 'test_customer',
        }]

        fake_urllib2 = FakeUrlib2Rss()
        rssAdaptor.urllib2 = fake_urllib2

        rss_adaptor = rssAdaptor.RSSAdaptor('http://examplerss/fiware_rss/')
        rss_adaptor.send_cdr(cdr)

        opener = fake_urllib2._opener
        self.assertEqual(opener._method, 'POST')
        self.assertEqual(opener._header, 'application/xml')
        self.assertEqual(opener._url, 'http://examplerss/fiware_rss/rss/cdrs')

        expected_xml = expected_xml.replace(' ', '')
        expected_xml = expected_xml.replace('\n', '')

        body = opener._body.replace(' ', '')
        body = body.replace('\n', '')
        self.assertEqual(expected_xml, body)