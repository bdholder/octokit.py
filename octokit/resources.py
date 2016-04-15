# -*- coding: utf-8 -*-

"""
octokit.resources
~~~~~~~~~~~~~~~~~

This module contains the workhorse of octokit.py, the Resources.
"""

from inflection import humanize, singularize
import requests
import uritemplate


_requests_keywords = {'method', 'url', 'headers', 'files', 'data', 'json', 'params', 'auth', 'cookies', 'hooks'}


class Resource(object):
    """The workhorse of octokit.py, this class makes the API calls and
    interprets them into an accessible schema. The API calls and schema parsing
    are lazy and only happen when an attribute of the resource is requested.
    """

    def __init__(self, session, name=None, url=None, schema=None,
                 response=None):
        self.etag = None
        self.session = session
        self._name = name
        self.url = url
        self.schema = schema
        self.response = response
        self.rels = {}

        if response:
            if response.content:
                self.schema = response.json()
            self.rels = self.parse_rels(response)
            self.url = response.url
            self.etag = response.headers.get('ETag')

        if type(self.schema) == dict and 'url' in self.schema:
            self.url = self.schema['url']


    def _parse_attribute(self, name):
        '''Package the requested attribute into a Resource if possible.'''
        if type(self.schema) == dict and type(name) == str:
            if name in self.schema:
                value = self.schema[name]
                if type(value) in {dict, list}:
                    # Smarter naming of Resource
                    if type(value) == dict and 'type' in value:
                        name = value['type']
                    return Resource(self.session, schema=value, name=humanize(name))
                else:
                    return value
            
            elif name + '_url' in self.schema:
                value = self.schema[name + '_url']
                # Do not attempt to process non-HTTP URLs
                if value[:5] == 'https':
                    return Resource(self.session, url=value, name=humanize(name))
                else:
                    return value
                
            raise AttributeError

        elif type(self.schema) == list and type(name) == int:
            # Assumption: lists always contain dicts
            return Resource(self.session, schema=self.schema[name], name=humanize(singularize(self._name)))
        else:
            #TODO: better error messages
            raise AttributeError


    def __getattr__(self, name):
        self.ensure_schema_loaded()
        return self._parse_attribute(name)


    def __getitem__(self, name):
        self.ensure_schema_loaded()
        return self._parse_attribute(name)


    def __call__(self, *args, **kwargs):
        return self.get(*args, **kwargs)

    def __repr__(self):
        name = self._name
        variables = self.variables()

        if variables:
            name += ' template'
            subtitle = ', '.join(variables)
        else:
            self.ensure_schema_loaded()
            schema_type = type(self.schema)
            if schema_type == dict:
                subtitle = ', '.join(self.schema.keys())
            elif schema_type == list:
                subtitle = str(len(self.schema))
            else:
                subtitle = str(self.schema)

        return '<Octokit %s(%s)>' % (name, subtitle)

    def variables(self):
        """Returns the variables the URI takes"""
        return uritemplate.variables(self.url) if self.url else set()

    def keys(self):
        """Returns the links this resource can follow"""
        self.ensure_schema_loaded()
        return self.schema.keys()

    def ensure_schema_loaded(self):
        """Check if resources' schema has been loaded, otherwise load it"""
        if self.schema:
            return

        variables = self.variables()
        if variables:
            raise Exception("You need to call this resource with variables %s"
                            % repr(list(variables)))

        self.sync()
        

    def parse_rels(self, response):
        """Parse relation links from the headers"""
        return {
          link['rel']: Resource(self.session, url=link['url'], name=self._name)
          for link in response.links.values()
        }

    def head(self, *args, **kwargs):
        """Make a HTTP HEAD request to the endpoint of resource."""
        return self.fetch_resource('HEAD', *args, **kwargs)

    def get(self, *args, **kwargs):
        """Make a HTTP GET request to the endpoint of resource."""
        return self.fetch_resource('GET', *args, **kwargs)

    def post(self, *args, **kwargs):
        """Make a HTTP POST request to the endpoint of resource."""
        return self.fetch_resource('POST', *args, **kwargs)

    def put(self, *args, **kwargs):
        """Make a HTTP PUT request to the endpoint of resource."""
        return self.fetch_resource('PUT', *args, **kwargs)

    def patch(self, *args, **kwargs):
        """Make a HTTP PATCH request to the endpoint of resource."""
        return self.fetch_resource('PATCH', *args, **kwargs)

    def delete(self, *args, **kwargs):
        """Make a HTTP DELETE request to the endpoint of resource."""
        return self.fetch_resource('DELETE', *args, **kwargs)

    def options(self, *args, **kwargs):
        """Make a HTTP OPTIONS request to the endpoint of resource."""
        return self.fetch_resource('OPTIONS', *args, **kwargs)

    def fetch_resource(self, method, *args, **kwargs):
        """Fetch the endpoint from the API and return it as a Resource.

        method         - HTTP method.
        *args          - Uri template argument
        **kwargs       – Uri template arguments
        """
        # Process requests keywords
        kwargs.pop('method', None)
        req_args = {}
        # Allow URL overriding
        req_args['url'] = kwargs.pop('url', self.url)
        for key in _requests_keywords:
            if key in kwargs:
                req_args[key] = kwargs.pop(key)

        # Expand all URI variables
        url_args = {}
        variables = self.variables()
        if len(args) == 1 and len(variables) == 1:
            url_args[next(iter(variables))] = args[0]
        else:
            for key in variables:
                url_args[key] = kwargs.pop(key, None)
        req_args['url'] = uritemplate.expand(req_args['url'], url_args)

        '''
        If there are any keyword arguments left, assume they are parameters
        if method is GET, otherwise throw them away.
        '''
        if method == 'GET':
            params = req_args.setdefault('params', {})
            params.update(kwargs)

        # If there is an ETag, add it to outgoing headers
        headers = req_args.setdefault('headers', {})
        headers['If-None-Match'] = self.etag

        request = requests.Request(method, **req_args)
        prepared_req = self.session.prepare_request(request)
        response = self.session.send(prepared_req)

        return Resource(self.session, response=response,
                        name=humanize(self._name))


    #TODO (bdholder) -- add docstring, add error handling for bad requests
    def sync(self):
        resource = self.get()
        response = resource.response

        self.response = response

        assert resource.response.status_code < 400

        self.etag = response.headers.get('ETag')
        # Schema will be empty if response was 304, so don't smash ours
        if resource.response.status_code != 304:
            self.schema = resource.schema
            self.rels = resource.rels
