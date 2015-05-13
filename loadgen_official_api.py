
import time
import loadgen
from loadgen import log

import keystoneclient, novaclient
from keystoneclient.openstack.common.apiclient.exceptions import AuthorizationFailure

# Pattern for keystone auth_url. The %s will be replaced with the configured host.
AUTH_URL_PATTERN = 'http://%s:35357/v2.0'

# Expected controller endpoint as returned by keystone. For now all our endpoints
# are configured to point to the 'controller' host.
EXPECTED_CONTROLLER_ENDPOINT = 'controller'

def check_args(args):
    from loadgen import check_params
    check_params(args,
        ['host', 'user', 'password', 'tenant'],
        { "fix_host": (str, "") })

class AuthenticatingLoadGenerator(loadgen.LoadGenerator):
    
    def __init__(self, args):
        check_args(args)
        super(AuthenticatingLoadGenerator, self).__init__(args)
        self.auth_url = AUTH_URL_PATTERN % args.host
        self.args = args
    
    def get_client_class(self):
        raise NotImplementedError("Abstract class")
    
    def client_module_name(self):
        raise NotImplementedError("Abstract class")
    
    def execute_client_request(self, client):
        raise NotImplementedError("Abstract class")
    
    def table_name(self):
        raise NotImplementedError("Abstract class")

    def create_session(self):
        client = self.create_client_session()
        if self.args.fix_host:
            log("Fixing all endpoints from %s to %s" % (EXPECTED_CONTROLLER_ENDPOINT, self.args.fix_host))
            self.fixEndpoints(client, EXPECTED_CONTROLLER_ENDPOINT, self.args.fix_host)
        return client

    def fixEndpoints(self, client, old_controller, new_controller):
        # Metaprogramming: Traverse all string-values in __dict__ and sub-dictionaries
        # of client-object, in all string-values, replace old_ with new_controller
        handled = list()
        depth = [0]
        def fix(o):
            if o in handled: return
            handled.append(o)
            if isinstance(o, dict):
                for key, value in o.iteritems():
                    if type(value) is str or type(value) is unicode:
                        if old_controller in value:
                            newvalue = value.replace(old_controller, new_controller)
                            log("Fixed endpoint: %s -> %s" % (value, newvalue))
                            o[key] = newvalue
                    else:
                        fix(value)
            elif isinstance(o, list):
                for v in o: fix(v)
            elif type(o).__module__.startswith(self.client_module_name()):
                fix(o.__dict__)
        fix(client)

class FullSessionGenerator(AuthenticatingLoadGenerator):
    """This generator creates a full session with each request, including complete authentication etc."""
    def __init__(self, args):
        self.create_query = "create table %s (start integer, authentication_time integer, request_time integer, error text);" % self.table_name()
        self.commit_query = "insert into %s values (?, ?, ?, ?);" % self.table_name()
        super(FullSessionGenerator, self).__init__(args)

    def execute_request(self):
        error = None
        authenticationTime = 0
        requestTime = 0
        try:
            start = time.time()
            client = self.create_session()
            authenticated = time.time()
            authenticationTime = authenticated - start
            self.execute_client_request(client)
            end = time.time()
            requestTime = end - authenticated
        except AuthorizationFailure, f:
            error = "AuthorizationFailure: %s" % f
        except Exception, e:
            error = "Exception: %s" %e
        finally:
            self.record_results((start, authenticationTime, requestTime, error))

class AuthenticateOnceGenerator(AuthenticatingLoadGenerator):
    """This generator authenticates once and then sends lightweight requests instead of re-authenticating each time."""
    def __init__(self, args):
        self.create_query = "create table %s (start integer, request_time integer, error text);" % self.table_name()
        self.commit_query = "insert into %s values (?, ?, ?);" % self.table_name()
        super(AuthenticateOnceGenerator, self).__init__(args)
        log("Creating session...")
        self.client = self.create_session()
    
    def execute_request(self):
        request_time = 0
        error = None
        try:
            start = time.time()
            self.execute_client_request(self.client)
            request_time = time.time() - start
        except Exception, e:
            error  = "Exception: %s" % e
            # TODO remove
            print error
        finally:
            self.record_results((start, request_time, error))

class KeystoneMixin(object):
    def execute_client_request(self, client):
        client.users.list()
    def create_client_session(self):
        klass = keystoneclient.v2_0.client.Client
        a = self.args
        return klass(auth_url=self.auth_url, username=a.user, password=a.password, tenant_name=a.tenant)
    def client_module_name(self):
        return "keystoneclient"
    def table_name(self):
        return "keystone"

class NovaMixin(object):
    def execute_client_request(self, client):
        client.flavors.list()
    def create_client_session(self):
        from novaclient.v1_1 import client
        a = self.args
        from keystoneclient.auth.identity import v2
        from keystoneclient import session
        from novaclient.client import Client
        auth = v2.Password(auth_url=self.auth_url,
                               username=a.user,
                               password=a.password,
                               tenant_name=a.tenant)
        sess = session.Session(auth=auth)
        return client.Client(service_type='compute', session=sess)
        
        # klass = novaclient.v1_1.client.Client
        # klass = client.Client
        # import pdb; pdb.set_trace()
        # return klass(auth_url = self.auth_url, username=a.user, api_key=a.password, project_id=a.tenant)
    def client_module_name(self):
        return "novaclient"
    def table_name(self):
        return "nova"

class NovaSessionGenerator(NovaMixin, FullSessionGenerator):
    pass

class NovaSimpleGenerator(NovaMixin, AuthenticateOnceGenerator):
    pass

class KeystoneSessionGenerator(KeystoneMixin, FullSessionGenerator):
    pass

class KeystoneSimpleGenerator(KeystoneMixin, AuthenticateOnceGenerator):
    pass

