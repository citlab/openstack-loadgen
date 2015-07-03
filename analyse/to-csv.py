#!/usr/bin/env python2

import sqlite3
import sys
import numpy as np
import matplotlib.pyplot as plt

def main(argv):
    if len(argv) != 1:
        print "Parameters: <sqlite3 database file>"
        sys.exit(1)
    db_file = argv[0]
    conn = sqlite3.connect(db_file)
    try:
        c = conn.cursor()
        def read_table(table, columns="*"):
            query = "select %s from %s;" % (columns, table)
            rows = c.execute(query).fetchall()
            return np.array(rows)
       
        tables = c.execute("select name from sqlite_master where type = 'table'").fetchall()
        tables = [ t[0] for t in tables ]
        tables = [ t for t in tables if t.startswith("analyse_") ]
        print "List of tables to analyse: %s" % ', '.join(tables)
        
        for table in tables:
            print "Converting %s" % table
            rows = read_table(table)
            csvdata = rows
            np.savetxt('%s.csv' % table, csvdata, delimiter=',')
    finally:
        conn.close()

if __name__ == "__main__":
    main(sys.argv[1:])

