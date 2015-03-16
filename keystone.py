
import sys, signal, sqlite3, time, os, threading

from keystoneclient.v2_0 import client
from keystoneclient.openstack.common.apiclient.exceptions import AuthorizationFailure

DATABASE_BASE = 'tests.sqlite'
DATABASE_SUFFIX = 'db'

BUFFERED_RESULTS = 100
NUM_WORKERS = 10

NUM_SECONDS = 0
# NUM_SECONDS = 20

requests_per_second = 5
PRODUCER_TIMEOUT = 0.2 # seconds

INCREMENT_REQUESTS = int(PRODUCER_TIMEOUT * requests_per_second)
PRODUCER_TIMEOUT = float(INCREMENT_REQUESTS) / requests_per_second # Adjust value to fix int-rounding above

def log(string):
    import datetime
    timestring = datetime.datetime.fromtimestamp(time.time()).strftime('%d.%m.%Y %H:%M:%S')
    print "%s: %s" % (timestring, string)
    sys.stdout.flush()

def main(argv):
    if len(argv) != 1:
        log("Need one argument: keystone host to connect to.")
        sys.exit(1)
    host = argv[0]
    
    klass = KeystoneUserList
    #klass = KeystoneAuthAndUserList
    l = klass(host)
    
    log("Running against %s" % l.auth_url)
    log("Starting worker threads...")
    l.create_production_worker()
    for _ in range(NUM_WORKERS):
        l.create_execution_worker()
    starttime = time.time()
    for thread in l.threads:
        thread.start()
    
    if NUM_SECONDS > 0:
        log("Running for %i seconds..." % NUM_SECONDS)
        threading.Timer(NUM_SECONDS, l.stop_running).start()
    else:
        log("Running until CTRL-C interrupt...")
        def signal_handler(signum, frame):
            log("Signal %s caught." % signum)
            l.stop_running()
        signal.signal(signal.SIGINT, signal_handler)
        signal.pause()
    
    l.finish_workers()
    l.flush_results()
    
    duration = l.last_request_end - starttime
    log("Executed %i requests in %.2f seconds. %.2f requests per second, %.2f milliseconds per request." \
                % (l.request_nr, duration, l.request_nr/duration, duration*1000/l.request_nr))

class DatabaseConnection(object):
    def __init__(self, generator, description="<unknown>", fatal=False):
        self.generator = generator
        self.description = description
        self.fatal = fatal
        self.connection = None
        self.cursor = None
    def __enter__(self):
        self.connection = sqlite3.connect(self.generator.database_name)
        self.cursor = self.connection.cursor()
        return self.cursor
    def __exit__(self, type, value, traceback):
        if value:
            log("Error during %s: %s" % (self.description, value))
        try:
            self.connection.commit()
        except Exception, e:
            log("Error during commit (of %s): %s" % (self.description, e))
        try:
            self.connection.close()
        except Exception, e:
            log("Error while closing connection (of %s): %s" % (self.description, e))
        if self.fatal and value:
            log("Fatal error, exiting.")
            sys.exit(1)

class LoadGenerator(object):

    def __init__(self):
        if self.commit_query is None:
            raise Exception("Need non-abstract subclass with commit_query attribute!")
        if self.create_query is None:
            raise Exception("Need non-abstract subclass with create_query attribute!")
        
        # Use a non-existing database-file
        self.database_name = DATABASE_BASE
        i = 0
        while True:
            self.database_name = "%s.%i.%s" % (DATABASE_BASE, i, DATABASE_SUFFIX)
            i += 1
            if not os.path.exists(self.database_name):
                break
        log("Writing to database %s" % self.database_name)
        
        # Create table for our measurements
        with self.connection(description="creating table", fatal=True) as c:
            c.execute(self.create_query)
        
        # Collection of data, shared array guarded by lock
        self.results = []
        self.results_lock = threading.Lock()
        self.results_buffer = BUFFERED_RESULTS
        
        # Some statistics
        self.request_nr = 0
        self.last_request_end = 0
        
        # Workers
        self.workers_running = True
        self.threads = []
        
        # Request management
        self.producer_timeout = PRODUCER_TIMEOUT
        self.requests_increment = INCREMENT_REQUESTS
        self.request_semaphore = threading.Semaphore(0)
    
    def connection(self, description="<unknown>", fatal=False):
        return DatabaseConnection(self, description, fatal)

    def record_results(self, values):
        flush_results = False
        try:
            self.results_lock.acquire()
            self.results.append(values)
            self.request_nr += 1
            if len(self.results) >= self.results_buffer:
                flush_results = True
                results_copy = list(self.results)
                self.results = []
        finally:
            self.results_lock.release()
        if flush_results:
            self.commit_results(results_copy)
    
    def flush_results(self):
        try:
            self.results_lock.acquire()
            results_copy = list(self.results)
            self.results = []
        finally:
            self.results_lock.release()
        self.commit_results(results_copy)
    
    def commit_results(self, values):
        if len(values) > 0:
            with self.connection(description="updating values") as c:
                log("Committing %i results" % len(values))
                c.executemany(self.commit_query, values)
    
    def execution_worker(self):
        while self.workers_running:
            self.request_semaphore.acquire()
            if self.workers_running:
                self.execute_request()
                self.last_request_end = time.time()
    
    def create_execution_worker(self):
        thread = threading.Thread(target = self.execution_worker)
        self.threads.append(thread)
    
    def create_production_worker(self):
        def produce():
            while self.workers_running:
                time.sleep(self.producer_timeout)
                if self.workers_running:
                    self.increment_requests()
        thread = threading.Thread(target = produce)
        self.threads.append(thread)
    
    def increment_requests(self):
        # Add X outstanding jobs to the "queue"
        for _ in range(self.requests_increment):
            self.request_semaphore.release()
    
    def finish_workers(self):
        for _ in range(len(self.threads)):
            # Wake up all threads that might be waiting
            # Important: workers_running must already be False!
            self.request_semaphore.release()
        for thread in self.threads:
            thread.join()
    
    def stop_running(self):
        log("Stopping workers...")
        self.workers_running = False
   
class KeystoneLoadGenerator(LoadGenerator):
    AUTH_URL_PATTERN = 'http://%s:35357/v2.0'
    user = 'admin'
    password = 'iep9Teig'
    tenant = 'admin'
    
    def __init__(self, auth_host):
        super(KeystoneLoadGenerator, self).__init__()
        self.auth_url = self.AUTH_URL_PATTERN % auth_host
    
    def create_keystone_session(self):
        return client.Client(auth_url=self.auth_url, \
               username=self.user, password=self.password, tenant_name=self.tenant)

class KeystoneAuthAndUserList(KeystoneLoadGenerator):
    create_query = "create table keystone (start integer, authentication_time integer, request_time integer, error text);"
    commit_query = "insert into keystone values (?, ?, ?, ?);"
    def execute_request(self):
        error = None
        authenticationTime = 0
        requestTime = 0
        try:
            start = time.time()
            keystone = self.create_keystone_session()
            authenticated = time.time()
            authenticationTime = authenticated - start
            keystone.users.list()
            end = time.time()
            requestTime = end - authenticated
        except AuthorizationFailure, f:
            error = "AuthorizationFailure: %s" % f
        except Exception, e:
            error = "Exception: %s" %e
        finally:
            self.record_results((start, authenticationTime, requestTime, error))

class KeystoneUserList(KeystoneLoadGenerator):
    create_query = "create table keystone (start integer, request_time integer, error text);"
    commit_query = "insert into keystone values (?, ?, ?);"
    def __init__(self, auth_host):
        super(KeystoneUserList, self).__init__(auth_host)
        try:
            log("Creating keystone session...")
            self.keystone = self.create_keystone_session()
        except Exception, e:
            log("Error creating keystone session: %s" % e)
    
    def execute_request(self):
        request_time = 0
        error = None
        try:
            start = time.time()
            self.keystone.users.list()
            request_time = time.time() - start
        except Exception, e:
            error  = "Exception: %s" % e
        finally:
            self.record_results((start, request_time, error))

if __name__ == "__main__":
    main(sys.argv[1:])

