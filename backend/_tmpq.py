import psycopg, json
conn = psycopg.connect('host=127.0.0.1 port=55432 dbname=financial_research user=frs password=frs_dev_password')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
print('USERS COLS:', [r[0] for r in cur.fetchall()])
cur.execute("SELECT * FROM users WHERE email=%s", ("mr.palpandii@gmail.com",))
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
print('USER MATCHES:', len(rows))
for r in rows:
    print(dict(zip(cols, r)))
cur.execute("SELECT COUNT(*) FROM workspaces"); print('WORKSPACES:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM documents"); print('DOCUMENTS:', cur.fetchone()[0])
cur.execute("SELECT id,name,owner_id,created_at FROM workspaces ORDER BY created_at")
print('WS LIST:')
for r in cur.fetchall(): print(r)
