import os
import unittest

import requests_mock
import uritemplate

import octokit

import json


root = {}
root['repository_url'] = 'https://api.github.com/repos/{owner}/{repo}'
root['user_repositories_url'] = 'https://api.github.com/users/{user}/repos{?type,page,per_page,sort}'
root['user_url'] = 'https://api.github.com/users/{user}'

user_octocat = {}
user_octocat['login'] = 'octocat'
user_octocat['type'] = 'User'
user_octocat['url'] = 'https://api.github.com/users/octocat'

user_gridbug = {}
user_gridbug['login'] = 'gridbug'
user_gridbug['url'] = 'https://api.github.com/users/gridbug'

user_lich = {}
user_lich['login'] = 'lich'
user_lich['url'] = 'https://api.github.com/users/lich'

repo_1 = {}
repo_1['git_url'] = 'git:github.com/octocat/Hello-World.git'
repo_1['issues_url'] = 'https://api.github.com/repos/octocat/Hello-World/issues{/number}'
repo_1['name'] = 'Hello-World'
repo_1['owner'] = user_octocat
repo_1['permissions'] = {'admin': False, 'push': False, 'pull': True}
repo_1['ssh_url'] = 'git@github.com:octocat/Hello-World.git'
repo_1['url'] = 'https://api.github.com/repos/octocat/Hello-World'

issue1 = {}
issue1['state'] = 'open'
issue1['url'] = 'https://api.github.com/repos/octocat/Hello-World/issues/1'
issue1['user'] = user_gridbug

issue2_part = {}
issue2_part['state'] = 'closed'
issue2_part['url'] = 'https://api.github.com/repos/octocat/Hello-World/issues/2'
issue2_part['user'] = user_gridbug

issue2 = dict(issue2_part)
issue2['closed_by'] = user_lich




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


@requests_mock.mock()
class TestResourceUsage(unittest.TestCase):
    def setUp(self):
        self.client = octokit.Client()
    

    def test_client_initialization(self, m):
        self.assertEqual(self.client.schema, {})


    def test_lazy_parsing(self, m):
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/repos/octocat/Hello-World', json=repo_1)

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        self.assertNotEqual(repo.schema, {})
        self.assertIs(type(repo.schema['owner']), dict)
        self.assertIsInstance(repo.owner, octokit.Resource)
        

    def test_chained_dots(self, m):
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/repos/octocat/Hello-World', json=repo_1)
        m.get('https://api.github.com/repos/octocat/Hello-World/issues', json=[issue1])

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        issues = repo.issues()
        issue0 = issues[0]
        self.assertIs(type(issue0.user), octokit.Resource)
        self.assertEqual(issue0.user.login, 'gridbug')


    def test_refresh(self, m):
        m.get('https://api.github.com', json=root)
        m.get(repo_1['url'], json=repo_1)
        m.get('https://api.github.com/repos/octocat/Hello-World/issues', json=[issue1])
        m.get('https://api.github.com/repos/octocat/Hello-World/issues?state=all', json=[issue1, issue2_part])
        m.get(issue2['url'], json=issue2)

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        issues = repo.issues(state='all')
        self.assertEqual(issues.url, 'https://api.github.com/repos/octocat/Hello-World/issues?state=all')
        issue = issues[1]
        self.assertTrue(issue.state, 'closed')
        self.assertFalse(hasattr(issue, 'closed_by'))
        issue.refresh()
        self.assertTrue(hasattr(issue, 'closed_by'))
        self.assertEqual(issue.closed_by.login, 'lich')

    
    def test_uri_template_parameter_stripping(self, m):
        m.get('https://api.github.com', json=root)

        self.assertEqual(self.client.user_repositories_url,
                         'https://api.github.com/users/{user}/repos{?type,page,per_page,sort}')
        r = self.client.user_repositories
        self.assertEqual(r.url, 'https://api.github.com/users/{user}/repos')


    def test_smart_naming(self, m):
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/repos/octocat/Hello-World', json=repo_1)

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        self.assertEqual(repo.owner.type, 'User')
        self.assertEqual(repo.owner._name, 'User')


    def test_ensure_schema_loaded_exception(self, m):
        """Test that ensure_schema_loaded raises correct exception."""
        m.get('https://api.github.com', json=root)

        try:
            #.id necessary to force accessing resource
            self.client.user.id
        except Exception as e:
            self.assertNotIsInstance(e, NameError)
            self.assertEqual(e.args[0], "You need to call this resource with variables ['user']")


    def test_keyword_routing(self, m):
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/users/octocat/repos?page=2', json={})

        x = self.client.user_repositories(user='octocat', page=2, headers={'custom-header': '42'})
        self.assertEqual(x.url, 'https://api.github.com/users/octocat/repos?page=2')


    def test_schema_key_aliasing(self, m):
        """Test Resource whether attributes alias schema keys."""
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/repos/octocat/Hello-World', json=repo_1)

        try:
            self.client.name
            self.fail(msg="No exception raised when accessing Client.name")
        except Exception as e:
            self.assertIsInstance(e, octokit.exceptions.NotFound)

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        self.assertEqual(repo.name, 'Hello-World')


    def test_non_https_uri_scheme(self, m):
        '''Test that non-HTTPS URI schemes are not processed into Resources.'''
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/repos/octocat/Hello-World', json=repo_1)

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        self.assertEqual(repo.git, repo_1['git_url'])
        self.assertEqual(repo.ssh, repo_1['ssh_url'])


    def test_schemas_without_url(self, m):
        '''Test that a schema without a URL does not break __repr__.'''
        m.get('https://api.github.com', json=root)
        m.get('https://api.github.com/repos/octocat/Hello-World', json=repo_1)

        repo = self.client.repository(owner='octocat', repo='Hello-World')
        try:
            repo.permissions.__repr__()
        except:
            self.fail(msg='Exception raise after __repr__ call.')


if __name__ == '__main__':
    unittest.main()
