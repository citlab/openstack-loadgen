
import sys, signal, sqlite3, time, os, threading

from keystoneclient.v2_0 import client
from keystoneclient.openstack.common.apiclient.exceptions import AuthorizationFailure

DATABASE_BASE = 'tests.sqlite'
DATABASE_SUFFIX = 'db'

# Number of results to buffer before writing them to the database.
BUFFERED_RESULTS = 100

# Number of threads creating requests. Requests-queue will stall if there are
# not enough workers or if requests take too long to come back.
NUM_WORKERS = 10

# Set this for timed execution - will terminate after this time
NUM_SECONDS = 0 # 20

# Rate (in seconds) at which new request-jobs are added to the queue.
# Determines the "granularity" of creating new requests
BASE_PRODUCER_TIMEOUT = 0.2

# Initial number of requests per second
REQUESTS_PER_SECOND = 1

# Set this to slowly increase the number of requests per second.
# Once in a fixed interval, the reqs_per_second are increased by a fixed value.
increase_production_speed = True
if increase_production_speed:
    PRODUCTION_SPEEDUP_TIMEOUT = 2*60
    PRODUCTION_SPEEDUP_INCREMENT = 1
else:
    PRODUCTION_SPEEDUP_TIMEOUT = 0

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
    log("Running with %i requests per second" % REQUESTS_PER_SECOND)
    log("Starting worker threads...")
    l.set_requests_per_second(REQUESTS_PER_SECOND)
    l.create_production_worker()
    if PRODUCTION_SPEEDUP_TIMEOUT > 0:
        log("Incrementing reqs_per_second by %i every %i seconds" % (PRODUCTION_SPEEDUP_INCREMENT, PRODUCTION_SPEEDUP_TIMEOUT))
        l.production_speedup_increment = PRODUCTION_SPEEDUP_INCREMENT
        l.production_speedup_timeout = PRODUCTION_SPEEDUP_TIMEOUT
        l.start_production_speedup_worker()
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
    seconds_per_req = duration*1000/l.request_nr if l.request_nr > 0 else 0
    reqs_per_second = l.request_nr/duration
    log("Executed %i requests in %.2f seconds. %.2f requests per second, %.2f milliseconds per request." \
                % (l.request_nr, duration, reqs_per_second, seconds_per_req))

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
        self.set_requests_per_second(1)
        self.production_speedup_timeout = 60
        self.production_speedup_increment = 1
        self.request_semaphore = threading.Semaphore(0)
    
    def connection(self, description="<unknown>", fatal=False):
        """Create a new database connection (use in with: statement)"""
        return DatabaseConnection(self, description, fatal)

    def record_results(self, values):
        """Add new results to the results buffer."""
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
        """Write all values currently in the results-buffer into the database."""
        try:
            self.results_lock.acquire()
            results_copy = list(self.results)
            self.results = []
        finally:
            self.results_lock.release()
        self.commit_results(results_copy)
    
    def commit_results(self, values):
        """Write the given values into the database."""
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
        for _ in range(self.producer_increment):
            self.request_semaphore.release()
   
    def start_production_speedup_worker(self):
        """This thread will be started as a daemon immediately due to the long sleep time"""
        def speedup_production():
            while self.workers_running:
                time.sleep(self.production_speedup_timeout)
                if self.workers_running:
                    reqs = self.requests_per_second()
                    reqs += self.production_speedup_increment
                    log("Setting requests_per_second to %i" % reqs)
                    self.set_requests_per_second(reqs)
        thread = threading.Thread(target = speedup_production)
        thread.daemon = True
        thread.start()
    
    def set_requests_per_second(self, requests_per_second):
        self.producer_increment = int(float(BASE_PRODUCER_TIMEOUT) * float(requests_per_second))
        if self.producer_increment <= 0: self.producer_increment = 1 
        self.producer_timeout = float(self.producer_increment) / float(requests_per_second) # Adjust value to fix int-rounding above
    
    def requests_per_second(self):
        return (1/self.producer_timeout) * self.producer_increment
   
    def finish_workers(self):
        for _ in range(len(self.threads)):
            # Wake up all threads that might be waiting
            # Important: workers_running must already be False!
            self.request_semaphore.release()
        for i, thread in enumerate(self.threads):
            # log("Waiting for %i threads..." % (len(self.threads) - i))
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

