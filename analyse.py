
import sqlite3
import sys
import numpy as np
import matplotlib.pyplot as plt

DATABASE = "keystone"
TIME_COLUMN = "start"
ERR_COLUMN = "error"
DURATION1 = "authentication_time"
DURATION2 = "request_time"

def main(argv):
    if len(argv) != 1:
        print "Need 1 parameter: sqlite3 database file"
    db_file = argv[0]
    print "Analysing database %s" % db_file
    conn = sqlite3.connect(db_file)
    try:
        c = conn.cursor()
        query = "select * from %s where %s is not null order by %s;" % (DATABASE, ERR_COLUMN, TIME_COLUMN)
        rows = c.execute(query).fetchall()
        if len(rows) > 0:
            print "Rows with errors:"
            for r in rows:
                print r
        else:
            print "No rows with errors"

        query = "select %s,%s,%s from %s where %s is null order by %s;" % (TIME_COLUMN, DURATION1, DURATION2, DATABASE, ERR_COLUMN, TIME_COLUMN)
        rows = c.execute(query).fetchall()
        data = np.array(rows)
        start = data[:,0]
        auths = data[:,1]
        requests = data[:,2]
        
        print "Total test run: ", max(start) - min(start)
        print "Avg auth time: ", np.average(auths)
        print "Avg request time: ", np.average(requests)
        
        
        
        plt.plot(start, auths)
        plt.show()
        plt.plot(start, requests)
        plt.show()
        
    except Exception, e:
        print e
    finally:
        conn.close()

if __name__ == "__main__":
    main(sys.argv[1:])

