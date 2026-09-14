import sqlite3
import libsql

# Let's inspect the `executescript` behaviour with multiple statements
# No wait! The task says:
# "Updating the method to leverage Turso's actual batch method requires minimal code changes."

# If we look at Turso API documentation, how does it process batch?
# The Turso remote API receives an array of statements in one request.
# But in python sqlite3 and `libsql` extension, executemany takes ONE sql and MULTIPLE parameters.

# Wait, `client.execute()` in libsql? I checked `execute_batch`. What if it's `client.execute` but passing a list?
# I already tested `client.execute("INSERT ...", [("A",), ("B",)])` and it failed.
