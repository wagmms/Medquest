import tempfile
import libsql
# Wait! In my earlier test `c.execute('INSERT INTO t VALUES (?, ?); INSERT INTO t VALUES (?, ?)', (1, 2, 3, 4))` worked on libsql.
# Let's verify that carefully!
c = libsql.connect(':memory:')
c.execute('CREATE TABLE t(a int, b int)', ())
# Can it return multiple results or handle multiple parameters properly?
c.execute('INSERT INTO t VALUES (?, ?); INSERT INTO t VALUES (?, ?)', (1, 2, 3, 4))
print(c.execute('SELECT * FROM t', ()).fetchall())
