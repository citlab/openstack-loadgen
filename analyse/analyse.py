#!/usr/bin/env python2

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
            numerrors = c.execute("select count(*) from errors").fetchall()[0][0]
            errors = c.execute("select distinct error from errors").fetchall()
            errors = [ e[0] for e in errors ]
            if len(errors) > 0:
                print "\nTotal number of errors: %i" % numerrors
                print "Distinct errors:"
                for r in errors: print r
                print
        except Exception, e:
            print "Error reading table 'errors': %s" % e
        
        tables = c.execute("select name from sqlite_master where type = 'table'").fetchall()
        tables = [ t[0] for t in tables ]
        print "List of tables: %s" % ', '.join(tables)
        tables = [ t for t in tables if t.startswith("analyse_") ]
        print "List of tables to analyse: %s" % ', '.join(tables)
        
        for table in tables:
            print "Analysing %s" % table
            rows = read_table(table)
            duration = rows[:,0]
            data = rows[:,1]
            print "Total test run duration: ", max(duration) - min(duration)
            print "Avg time: ", np.average(data)
            plt.plot(duration, data)
            plt.show()
    finally:
        conn.close()

if __name__ == "__main__":
    main(sys.argv[1:])

