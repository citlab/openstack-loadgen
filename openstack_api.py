
import requests, json

KEYSTONE_PUBLIC_PORT = 5000
KEYSTONE_ADMIN_PORT = 35357

def enable_http_debugging():
    import httplib
    httplib.HTTPConnection.debuglevel = 1

class Endpoint(object):
    ADMIN = object()
    INTERNAL = object()
    PUBLIC = object()
    
    def __init__(self, admin, internal, public, default=None):
        if not default: default = Endpoint.PUBLIC
        self.default = default
        self.admin = Endpoint.fix_url(admin)
        self.internal = Endpoint.fix_url(internal)
        self.public = Endpoint.fix_url(public)
    
    @staticmethod
    def from_json(json, default=None):
        admin = Endpoint.fix_url(json["adminURL"])
        internal = Endpoint.fix_url(json["internalURL"])
        public = Endpoint.fix_url(json["publicURL"])
        return Endpoint(admin, internal, public, default)

    @staticmethod
    def fix_url(url):
        if url[-1] != '/':
            url += '/'
        return url
   
    @staticmethod
    def change_url_host(url_str, new_host):
        import urlparse
        url = urlparse.urlparse(url_str)
        replaced = url._replace(netloc="{}:{}".format(new_host, url.port))
        return replaced.geturl()

    @staticmethod
    def change_url_path(url_str, new_path):
        import urlparse
        url = urlparse.urlparse(url_str)
        replaced = url._replace(path=new_path)
        return replaced.geturl()

    def fix_host(self, new_host):
        self.admin = Endpoint.change_url_host(self.admin, new_host)
        self.internal = Endpoint.change_url_host(self.internal, new_host)
        self.public = Endpoint.change_url_host(self.public, new_host)

    def __getitem__(self, index):
        if index is Endpoint.ADMIN:
            return self.admin
        elif index is Endpoint.INTERNAL:
            return self.internal
        elif index is Endpoint.PUBLIC:
            return self.public
        else:
            raise IndexError("Illegal Endpoint type marker: %r" % index)

    def __str__(self):
        return self[self.default]
    def __repr__(self):
        return self.__str__()

class OpenstackApi(object):
    def __init__(self, session=None, endpoint=None):
        self.session = session
        self.endpoint = endpoint
        self.do_authenticate = True
    
    def set_endpoint(self, new_endpoint):
        self.endpoint = new_endpoint

    def set_session(self, new_session):
        self.session = new_session

    def is_authenticated(self):
        return self.session is not None and self.session.is_authenticated()

    def add_token(self, headers):
        if not self.do_authenticate:
            return
        if self.is_authenticated():
            headers["X-Auth-Token"] = self.session.token_id()

    def check_response(self, r):
        r.raise_for_status()

    def basic_get(self, url, params, headers):
        r = requests.get(url, params=params, headers=headers)
        self.check_response(r)
        return r.json()
    
    def get(self, path, params={}):
        assert self.endpoint, "endpoint attribute is required."
        headers = {}
        self.add_token(headers)
        return self.basic_get(str(self.endpoint) + path, params, headers)
    
    def post(self, path, data={}):
        assert self.endpoint, "endpoint attribute is required."
        headers = { "Content-Type": "application/json" }
        self.add_token(headers)
        r = requests.post(str(self.endpoint) + path, data=json.dumps(data), headers=headers)
        self.check_response(r)
        return r.json()

    def versions(self, overwrite_host=None):
        """Almost every Openstack API supports listing API versions on the default path"""
        url = Endpoint.change_url_path(self.endpoint, '')
        versions = self.basic_get(url, {}, {})
        versions = self.parse_versions(versions)
        result = {}
        for version in versions:
            versionid = version["id"]
            links = [ x for x in version["links"] if x["rel"] == "self" ]
            if len(links) == 0:
                continue
            elif len(links) > 1:
                print "Warning: Multiple identity endpoints for version %s, using first. Endpoints: %s" % (versionid, endpoints)
            endpoint = links[0]["href"]
            if overwrite_host is not None:
                endpoint = Endpoint.change_url_host(endpoint, overwrite_host)
            result[versionid] = Endpoint.fix_url(endpoint)
        return result

    def parse_versions(self, versions):
        # Hook for APIs with special version JSON data
        return versions["versions"]

class BasicIdentityApi(OpenstackApi):
    def __init__(self, host=None, port=None, endpoint=None):
        if not endpoint:
            assert host, "Either endpoint or host parameter is required"
            if not port: port = KEYSTONE_PUBLIC_PORT
            endpoint = "http://%s:%i/" % (host, port)
        super(BasicIdentityApi, self).__init__(None, endpoint)
    
    def parse_versions(self, versions):
        return versions["versions"]["values"]

    def token(self, tenant, user, password):
        data = {
            "auth": {
                "tenantName": tenant,
                "passwordCredentials": {
                    "username": user,
                    "password": password
                }
            }
        }
        r = self.post("tokens", data=data)
        a = r["access"]
        raw_services = a["serviceCatalog"]
        services = {}
        for service in raw_services:
            t = service["type"]
            endpoints = service["endpoints"]
            if t in services or len(endpoints) > 1:
                print "Warning: Multiple endpoints for service type %s." % t
            services[t] = Endpoint.from_json(endpoints[0])
        return (a["token"], services, a["user"], a["metadata"])

def authenticated(func):
    def decorated(self, *args, **kwargs):
        if not self.is_authenticated():
            raise Exception("Not authenticated yet.")
        return func(self, *args, **kwargs)
    return decorated

class KeystoneSession(object):
    def __init__(self, identity_host=None, identity_port=None, identity_endpoint=None, identity_version="v2.0"):
        self.token = self.services = self.user = self.meta = None
        self.api = BasicIdentityApi(host=identity_host, port=identity_port, endpoint=identity_endpoint)
        versions = self.api.versions()
        if identity_version not in versions:
            raise Exception("Version %s not supported by endpoint '%s'. Supported versions: %s" % (identity_version, self.api.endpoint, versions.keys()))
        endpoint = versions[identity_version]
        self.api.set_endpoint(str(endpoint))
        self.service_apis = {}

    def is_authenticated(self):
        return self.token is not None

    def authenticate(self, tenant, user, password, overwrite_host=None):
        self.token, self.services, self.user, self.meta = self.api.token(tenant, user, password)
        if overwrite_host:
            # This is a hack in order to work with an OpenStack system which delivers wrong host names
            for endpoint in self.services.values():
                endpoint.fix_host(overwrite_host)
   
    @authenticated
    def token_id(self):
        return self.token["id"]
    
    @authenticated
    def tenant_id(self):
        return self.token["tenant"]["id"]

    @authenticated
    def get_endpoint(self, service_type):
        if service_type not in self.services:
            raise Exception("No endpoint found for service type %s" % service_type)
        return self.services[service_type]

    @authenticated
    def get_api(self, service_type, endpoint_type=None):
        if service_type in self.service_apis:
            endpoint_map = self.service_apis[service_type]
        else:
            endpoint_map = {}
            self.service_apis[service_type] = endpoint_map
        if not endpoint_type:
            if len(endpoint_map) == 0:
                klass = self._get_service_api_class(service_type)
                endpoint_type = klass.default_endpoint_type
                instance = klass(self)
                endpoint_map[endpoint_type] = instance
            elif len(endpoint_map) == 1:
                instance = endpoint_map.values()[0]
            else:
                raise Exception("Multiple endpoint_types for service %s available, but no endpoint_type specified." % service_type)
        else:
            if endpoint_type in endpoint_map:
                instance = endpoint_map[endpoint_type]
            else:
                klass = self._get_service_api_class(service_type)
                instance = klass(self, endpoint_type = endpoint_type)
                endpoint_map[endpoint_type] = instance
        return instance
    
    def _get_service_api_class(self, service_type):
        api_klasses = KeystoneSession.get_all_api_classes()
        for klass in api_klasses:
            if service_type in klass.supported_service_types:
                return klass
        raise Exception("No API class found for service type %s" % service_type)

    @staticmethod
    def get_all_api_classes():
        def all_subclasses(cls):
            return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in all_subclasses(s)]
        return all_subclasses(AuthenticatedOpenstackApi)

    @staticmethod
    def get_all_service_types():
        import operator
        api_klasses = KeystoneSession.get_all_api_classes()
        return set(reduce(operator.concat, [ x.supported_service_types for x in api_klasses ]))

class AuthenticatedOpenstackApi(OpenstackApi):
    supported_service_types = []
    default_service_type = None
    default_version = None
    default_endpoint_type = Endpoint.PUBLIC
    
    def __init__(self, session, service_type=None, endpoint_type=None, version=None):
        if not service_type:
            assert self.default_service_type, "default_service_type must be set by subclasses!"
            service_type = self.default_service_type
        if not version:
            assert self.default_version, "default_version must be set by subclasses!"
            version = self.default_version
        if not endpoint_type:
            endpoint_type = self.default_endpoint_type
        endpoint = session.get_endpoint(service_type)[endpoint_type]
        self.service_type = service_type
        self.endpoint_type = endpoint_type
        super(AuthenticatedOpenstackApi, self).__init__(session=session, endpoint=endpoint)
        try:
            self.check_endpoint(version)
        except:
            # Not all subclasses support versions() method
            pass
    
    def example(self):
        raise NotImplementedException("No example API-call implemented for this API.")
    
    def check_endpoint(self, version):
        versions = self.versions()
        if version not in versions:
            raise Exception("Version %s not supported for %s service. Available versions: %s" % (version, self.service_type, versions.keys()))
        endpoint = versions[version]
        if self.endpoint.startswith(endpoint):
            # My endpoint is an "extension" of the returned endpoint. This is ok.
            pass
        else:
            print "Fixing %s (version %s) endpoint from %s to %s" % (self.service_type, version, self.endpoint, endpoint)
            self.endpoint = endpoint

class IdentityAdminApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "identity" ]
    default_service_type = "identity"
    default_endpoint_type = Endpoint.ADMIN
    default_version = "v2.0" # v2.0 v2.0-admin v2.0-extensions v3 v3-extensions
    
    def parse_versions(self, versions):
        return versions["versions"]["values"]
    
    @authenticated
    def users(self):
        return [ x["username"] for x in self.get("users")["users"] ]
    example = users

class ComputeApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "compute" ]
    default_service_type = "compute"
    default_version = "v2.0" # + v2.0-extensions + v2.1
    
    @authenticated
    def servers(self):
        return [ x["name"] for x in self.get("servers")["servers"] ]
    example = servers

class ImageApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "image" ]
    default_service_type = "image"
    default_version = "v1.1" # v2.1
    
    @authenticated
    def images(self):
        return [ x["name"] for x in self.get("images")["images"] ]
    example = images

class VolumeApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "volume" ]
    default_service_type = "volume"
    default_version = "v2.0" # + v1.0

    @authenticated
    def volumes(self):
        return [ x["name"] for x in self.get("volumes")["volumes"] ]
    example = volumes

class NetworkApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "network" ]
    default_service_type = "network"
    default_version = "v2.0" # + v2.0 extensions

    @authenticated
    def networks(self):
        return [ x["name"] for x in self.get('networks')["networks"] ]
    example = networks

    def network_list(self):
        networks = self.networks()
        return { n["id"]: n["name"] for n in networks }

class ObjectStorageApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "object-store" ]
    default_service_type = "object-store"
    default_version = "v1.0"
    
    @authenticated
    def containers(self):
        return [ x["name"] for x in self.get("") ]
    example = containers

    def versions(self):
        raise Exception("Object Storage API does not support versions")

class OrchestrationApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "orchestration" ]
    default_service_type = "orchestration"
    default_version = "v1.0"
    
    @authenticated
    def stacks(self):
        return [ x["stack_name"] for x in self.get("stacks") ]
    example = stacks

class TelemetryApi(AuthenticatedOpenstackApi):
    supported_service_types = [ "telemetry" ]
    default_service_type = "telemetry"
    default_version = "v2.0"
    
    @authenticated
    def alarms(self):
        return [ x["name"] for x in self.get('alarms') ]
    example = alarms
    
    def versions(self):
        raise Exception("Telemetry API does not support versions")

if __name__ == "__main__":
    #enable_http_debugging()
    ip = "130.149.249.254"
    s = KeystoneSession(identity_host=ip)
    s.authenticate("clearwater", "admin", "iep9Teig", overwrite_host=ip)

    for api in KeystoneSession.get_all_service_types():
        try:
            print " === Checking %s" % api
            print s.get_api(api).example()
        except Exception, e:
            #import traceback
            #traceback.print_exc()
            print e
        print

