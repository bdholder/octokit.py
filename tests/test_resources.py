import os
import unittest

import requests_mock
import uritemplate

import octokit


class TestResources(unittest.TestCase):
    """Tests the functionality in octokit/resources.py"""

    def setUp(self):
        self.client = octokit.Client(api_endpoint='mock://api.com/{param}')
        self.adapter = requests_mock.Adapter()
        self.client.session.mount('mock', self.adapter)

    def test_call(self):
        """Test that resources.__call__ performs a HTTP GET"""
        url = uritemplate.expand(self.client.url, {'param': 'foo'})
        self.adapter.register_uri('GET', url, text='{"success": true}')

        response = self.client(param='foo')
        assert response.success

        # test named param inference
        response = self.client('foo')
        assert response.success

    def test_httpverb(self):
        """Test that each HTTP verb works properly when JSON is returned."""
        verbs_to_methods = [
            ('GET', self.client.get),
            ('POST', self.client.post),
            ('PUT', self.client.put),
            ('PATCH', self.client.patch),
            ('DELETE', self.client.delete),
            ('HEAD', self.client.head),
            ('OPTIONS', self.client.options),
        ]

        for verb, method in verbs_to_methods:
            url = uritemplate.expand(self.client.url, {'param': 'foo'})
            self.adapter.register_uri(verb, url, text='{"success": true}')

            response = method(param='foo')
            assert response.success

            # test named param inference
            response = method('foo')
            assert response.success

    def test_ensure_schema_loaded_exception(self):
        """Test that ensure_schema_loaded raises correct exception."""
        client = octokit.Client()
        try:
            #.id necessary to force accessing resource
            client.user.id
        except Exception as e:
            self.assertNotIsInstance(e, NameError)
            self.assertEqual(e.args[0], "You need to call this resource with variables ['user']")

    def test_schema_key_aliasing(self):
        """Test Resource whether attributes alias schema keys."""
        try:
            self.client.name
            self.assertTrue(False, msg="No exception raised when accessing Client.name")
        except Exception as e:
            self.assertEqual(e.args[0], "You need to call this resource with variables ['param']")

        schema = {'name': 'octocat'}
        r = octokit.Resource(None, name='Dummy', schema=schema)
        self.assertEqual(r.name, 'octocat')

if __name__ == '__main__':
    unittest.main()
