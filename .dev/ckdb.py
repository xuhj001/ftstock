import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
for row in c.execute("select host_key, name, length(value), length(encrypted_value), is_httponly from cookies where host_key like '%futunn.com'"):
    print(row)
