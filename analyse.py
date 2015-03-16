
import sqlite3
import sys
import numpy as np
import matplotlib.pyplot as plt

DATABASE = "keystone"
TIME_COLUMN = "start"
ERR_COLUMN = "error"

def main(argv):
    if len(argv) != 2:
        print "Need 2 parameters: sqlite3 database file, column to analyse"
        sys.exit(1)
    db_file = argv[0]
    ANALYSE_COLUMN = argv[1]
    print "Analysing %s.%s in database-file %s" % (DATABASE, ANALYSE_COLUMN, db_file)
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

        query = "select %s,%s from %s where %s is null order by %s;" % (TIME_COLUMN, ANALYSE_COLUMN, DATABASE, ERR_COLUMN, TIME_COLUMN)
        rows = c.execute(query).fetchall()
        data = np.array(rows)
        start = data[:,0]
        times = data[:,1]
        
        print "Total test run: ", max(start) - min(start)
        print "Avg time: ", np.average(times)
        
        plt.plot(start, times)
        plt.show()
        
    except Exception, e:
        print e
    finally:
        conn.close()

if __name__ == "__main__":
    main(sys.argv[1:])

