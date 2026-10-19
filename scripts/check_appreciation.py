import sys
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/uppcl_monitor.db')
c = conn.cursor()
c.execute("SELECT post_id, author_username, picked_status, complaint_type, text FROM processed_posts WHERE picked_status = 'APPRECIATION'")
rows = c.fetchall()
print(f"Total APPRECIATION posts in DB: {len(rows)}")
for r in rows:
    print(f"ID: {r[0]} | @{r[1]} | Type: {r[2]}/{r[3]}")
    print(f"   Text: {r[4]}")
conn.close()
