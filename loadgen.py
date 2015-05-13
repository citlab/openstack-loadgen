
import sys, signal, sqlite3, time, os, threading, multiprocessing, argparse

# Number of results to buffer before writing them to the database.
BUFFERED_RESULTS = 400

# Number of threads creating requests. Requests-queue will stall if there are
# not enough workers or if requests take too long to come back.
NUM_WORKERS = 100

# Rate (in seconds) at which new request-jobs are added to the queue.
# Determines the "granularity" of creating new requests
BASE_PRODUCER_TIMEOUT = 0.2

def log(string):
    import datetime
    timestring = datetime.datetime.fromtimestamp(time.time()).strftime('%d.%m.%Y %H:%M:%S')
    print "%s: %s" % (timestring, string)
    sys.stdout.flush()

def get_database_name():
    # Find a non-existing database-file
    DATABASE_BASE = 'tests.sqlite'
    DATABASE_SUFFIX = 'db'
    database_name = DATABASE_BASE
    i = 0
    while True:
        database_name = "%s.%i.%s" % (DATABASE_BASE, i, DATABASE_SUFFIX)
        i += 1
        if not os.path.exists(database_name):
            break
    return database_name

# For request generator parameters
def check_params(args, required=[], optional={}):
    ok = True
    for param in required:
        if not hasattr(args, param):
            print "Missing request generator parameter: %s" % param
            ok = False
    for param, (typ, default) in optional.items():
        if hasattr(args, param):
            value = getattr(args, param)
            try:
                typevalue = typ(value)
            except Exception, e:
                print "Failed to convert request generator parameter %s to type %s" % (param, t)
                ok = False
        else:
            setattr(args, param, default)
    if not ok:
        raise Exception("Error(s) parsing load generator parameters.")

def safe_tablename(string):
    # Remove every non-alphanumeric character to get a safe sql identifier.
    import re
    pattern = re.compile('[\W_]+')
    return pattern.sub('', string)

def main(argv):
    parser = argparse.ArgumentParser(description='Execute certain requests and log the results to a sqlite file.')
    parser.add_argument('-k', '--klass', required=True, type=str, help='Fully qualified Python class to use as request generator. The class must subclass LoadGenerator and conform to a certain API.')
    parser.add_argument('-p', '--params', type=str, nargs='*', help='Parameters to pass to the request generator class in the form of key=value pairs. All values will be collected and passed to the constructor.')
    parser.add_argument('-d', '--db', type=str, help='Database file to use. Must be non-existing. tests.sqlite.*.db is used by default.')
    parser.add_argument('-t', '--timeout', default=0, type=int, help='Timeout in seconds, after which the experiment is stopped automatically.')
    parser.add_argument('-r', '--requests_per_second', default=2, type=int, help='Requests fired per second. Combined with -i, this is the initial requests-per-second value.')
    parser.add_argument('-i', '--requests_increment', default=0, type=int, help='Additional number of requests added each speedup-interval (set by -I).')
    parser.add_argument('-I', '--requests_increment_timeout', default=120, type=int, help='Number of seconds before increasing the requests per second. Only applied when -i is larger then zero.')
    args = parser.parse_args()
    if args.params:
        for param in args.params:
            components = param.split('=')
            if len(components) != 2:
                print "Illegal key=value parameter: %s" % param
                return 1
            key, value = components
            setattr(args, key, value)
    
    # ======== Prepare the database
    database_name = args.db or get_database_name()
    if os.path.exists(database_name):
        print "Database file %s already exists." % database_name
        return 1
    args.db = database_name

    # ======== Create the request generator object
    import operator
    try:
        components = args.klass.split('.')
        if len(components) < 2:
            print "Request generator class not fully qualified class name: %s" % args.klass
            return 1
        classname = components[-1]
        mod = __import__(reduce(operator.concat, components[:-1]), fromlist=[classname])
        klass = getattr(mod, classname)
        l = klass(args)
    except Exception, e:
        print "Error importing class %s" % args.klass
        print e
        import traceback
        traceback.print_exc()
        return 1
    
    # ======== Create and start worker threads
    log("Running against %s" % l.auth_url)
    log("Running with %i requests per second" % args.requests_per_second)
    log("Starting worker threads...")
    l.set_requests_per_second(args.requests_per_second)
    l.create_production_worker()
    if args.requests_increment > 0:
        log("Incrementing requests_per_second by %i every %i seconds" % (args.requests_increment, args.requests_increment_timeout))
        l.production_speedup_increment = args.requests_increment
        l.production_speedup_timeout = args.requests_increment_timeout
        l.start_production_speedup_worker()
    for _ in range(NUM_WORKERS):
        l.create_execution_worker()
    starttime = time.time()
    for thread in l.threads:
        thread.start()
    
    # ======== Set up termination
    if args.timeout > 0:
        def kill_self():
            own_pid = multiprocessing.current_process().pid
            log("Sending SIGINT to current process (%i)" % own_pid)
            os.kill(own_pid, signal.SIGINT)
        log("Terminating automatically after %i seconds..." % args.timeout)
        timer = threading.Timer(args.timeout, kill_self)
        timer.daemon = True
        timer.start()
    log("Press CTRL-C to interrupt (or kill -INT ...)...")
    def signal_handler(signum, frame):
        log("Signal %s caught." % signum)
        l.stop_running()
    signal.signal(signal.SIGINT, signal_handler)
    # Wait for SIGINT from outside or from timer
    signal.pause()
    
    # ======== Wait for threads and write last results
    l.finish_workers()
    l.flush_results()
    
    # ======== Output some lowlevel statistics
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

    def __init__(self, args):
        self.args = args
        if self.commit_query is None:
            raise Exception("Need non-abstract subclass with commit_query attribute!")
        if self.create_query is None:
            raise Exception("Need non-abstract subclass with create_query attribute!")
        
        self.database_name = args.db
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
   
    def execute_request(self):
        raise NotImplementedError("Subclasses must implemente execute_request method")

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
        for i, thread in enumerate(self.threads):
            # log("Waiting for %i threads..." % (len(self.threads) - i))
            thread.join()
    
    def stop_running(self):
        log("Stopping workers...")
        self.workers_running = False
        for _ in range(len(self.threads)):
            # Wake up all threads that might be waiting
            self.request_semaphore.release()

if __name__ == "__main__":
    main(sys.argv[1:])

