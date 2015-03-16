
import sqlite3
import sys
import numpy as np
import matplotlib.pyplot as plt

def main(argv):
    if len(argv) != 1:
        print "Need 1 parameter: sqlite3 database file"
        sys.exit(1)
    db_file = argv[0]
    conn = sqlite3.connect(db_file)
    try:
        c = conn.cursor()
        def read_table(table, columns="*"):
            query = "select %s from %s;" % (columns, table)
            rows = c.execute(query).fetchall()
            return np.array(rows)
       
        try:
            errors = read_table("errors")
            if len(errors) > 0:
                print "Rows with errors:"
                for r in errors: print r
        except Exception, e:
            print "Error reading table 'errors': %s" % e
        
        tables = c.execute("select name from sqlite_master where type = 'table'").fetchall()
        tables = [ t[0] for t in tables ]
        print "List of tables: %s" % tables
        tables = [ t for t in tables if t.startswith("analyse_") ]
        print "List of tables to analyse: %s" % tables
        
        for table in tables:
            print "Analysing %s" % table
            rows = read_table(table)
            seconds = rows[:,0]
            data = rows[:,1]
            print "Total test run seconds: ", max(seconds) - min(seconds)
            print "Avg time: ", np.average(data)
            plt.plot(seconds, data)
            plt.show()
    
    except Exception, e:
        print e
    finally:
        conn.close()

if __name__ == "__main__":
    main(sys.argv[1:])

