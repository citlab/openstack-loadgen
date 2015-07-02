
import time
import loadgen
from loadgen import log
import openstack_api as api

def check_args(args):
    from loadgen import check_params
    check_params(args,
        [ 'service', 'host', 'user', 'password', 'tenant' ],
        { 'fix_host': (str, ""), 'timeout': (int, 5) })

class OpenstackRequestGenerator(loadgen.LoadGenerator):
    def __init__(self, args):
        check_args(args)
        self.args = args
        table = loadgen.safe_tablename(args.service)
        self.create_query = "create table %s (start integer, request_time integer, error text);" % table
        self.commit_query = "insert into %s values (?, ?, ?);" % table
        super(OpenstackRequestGenerator, self).__init__(args)
        log("Creating session...")
        self.session, self.api = self.create_session()
        self.auth_url = self.api.endpoint

    def create_session(self):
        s = api.KeystoneSession(identity_host=self.args.host)
        overwrite_host = self.args.fix_host if self.args.fix_host else None
        s.authenticate(self.args.tenant, self.args.user, self.args.password, overwrite_host=overwrite_host)
        a = s.get_api(self.args.service)
        a.timeout = self.args.timeout
        return s, a

    def execute_request(self):
        request_time = 0
        error = None
        try:
            start = time.time()
            self.execute_client_request(self.api)
            request_time = time.time() - start
        except Exception as e:
            error  = "Exception: %s" % e
            log(error)
        finally:
            self.record_results((start, request_time, error))

    def execute_client_request(self, api):
        return api.example()

