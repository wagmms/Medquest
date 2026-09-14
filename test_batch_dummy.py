import libsql
try:
    c = libsql.connect("http://dummy.com")
    c.batch(["SELECT 1"])
except Exception as e:
    print(e)
