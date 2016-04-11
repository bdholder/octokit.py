import os
import unittest

import requests_mock
import uritemplate

import octokit

import json


fake_server_1 = requests_mock.Adapter()

root = {}
root['repository_url'] = 'mock://api.com/repos/{owner}/{repo}'
root['user_repositories_url'] = 'mock://api.com/users/{user}/repos{?type,page,per_page,sort}'
fake_server_1.register_uri('GET', 'mock://api.com/', text=json.dumps(root))

user_octocat = {}
user_octocat['login'] = 'octocat'
user_octocat['type'] = 'User'
user_octocat['url'] = 'mock://api.com/users/octocat'

user_gridbug = {}
user_gridbug['login'] = 'gridbug'
user_gridbug['url'] = 'mock://api.com/users/gridbug'

user_lich = {}
user_lich['login'] = 'lich'
user_lich['url'] = 'mock://api.com/users/lich'

repo_1 = {}
repo_1['name'] = 'Hello-World'
repo_1['owner'] = user_octocat
repo_1['issues_url'] = 'mock://api.com/repos/octocat/Hello-World/issues{/number}'
repo_1['url'] = 'mock://api.com/repos/octocat/Hello-World'
fake_server_1.register_uri('GET', repo_1['url'], text=json.dumps(repo_1))

issue1 = {}
issue1['state'] = 'open'
issue1['url'] = 'mock://api.com/repos/octocat/Hello-World/issues/1'
issue1['user'] = user_gridbug

issue2_partial = {}
issue2_partial['state'] = 'closed'
issue2_partial['url'] = 'mock://api.com/repos/octocat/Hello-World/issues/2'
issue2_partial['user'] = user_gridbug

issue2 = dict(issue2_partial)
issue2['closed_by'] = user_lich
fake_server_1.register_uri('GET', issue2['url'], text=json.dumps(issue2))

fake_server_1.register_uri('GET', 'mock://api.com/repos/octocat/Hello-World/issues',
                                  text=json.dumps([issue1]))
fake_server_1.register_uri('GET', 'mock://api.com/repos/octocat/Hello-World/issues?state=all',
                                  text=json.dumps([issue1, issue2_partial]))



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


class TestResourceUsage(unittest.TestCase):
    def setUp(self):
        self.client = octokit.Client(api_endpoint='mock://api.com/')
        self.client.session.mount('mock', fake_server_1)


    def test_client_initialization(self):
        self.assertEqual(self.client.schema, {})


    def test_lazy_parsing(self):
        repo = self.client.repository(owner='octocat', repo='Hello-World')
        self.assertNotEqual(repo.schema, {})
        self.assertIs(type(repo.schema['owner']), dict)
        self.assertIsInstance(repo.owner, octokit.Resource)
        

    def test_chained_dots(self):
        repo = self.client.repository(owner='octocat', repo='Hello-World')
        issues = repo.issues()
        issue0 = issues[0]
        self.assertIs(type(issue0.user), octokit.Resource)
        self.assertEqual(issue0.user.login, 'gridbug')


    def test_refresh(self):
        # Necessary because requests_mock does not handle parameters correctly
        issues = octokit.Resource(self.client.session, name='Issues',
                                  url='mock://api.com/repos/octocat/Hello-World/issues?state=all')
        issues.refresh()
        issue = issues[1]
        self.assertTrue(issue.state, 'closed')
        self.assertFalse(hasattr(issue, 'closed_by'))
        issue.refresh()
        self.assertTrue(hasattr(issue, 'closed_by'))
        self.assertEqual(issue.closed_by.login, 'lich')

    
    def test_uri_template_parameter_stripping(self):
        self.assertEqual(self.client.user_repositories_url, 'mock://api.com/users/{user}/repos{?type,page,per_page,sort}')
        r = self.client.user_repositories
        self.assertEqual(r.url, 'mock://api.com/users/{user}/repos')


    def test_smart_naming(self):
        repo = self.client.repository(owner='octocat', repo='Hello-World')
        self.assertEqual(repo.owner.type, 'User')
        self.assertEqual(repo.owner._name, 'User')


    # TODO: automated testing for keyword routing to correct arguments
    

if __name__ == '__main__':
    unittest.main()
