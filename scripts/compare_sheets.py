import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests, csv, io, sqlite3, re

# 1. Fetch manual reference sheet
url = 'https://docs.google.com/spreadsheets/d/1shjWcK69y0S7pIHI-2V5Wh6c2SSSQBKcpgprmPbeNe8/export?format=csv&gid=283417465'
resp = requests.get(url)
manual_rows = list(csv.reader(io.StringIO(resp.text)))[2:]

manual_posts = {}
for idx, r in enumerate(manual_rows):
    if len(r) > 4 and r[4]:
        link = r[4].strip()
        m = re.search(r'status/(\d+)', link)
        if m:
            p_id = m.group(1)
            manual_posts[p_id] = {
                'row': idx + 3,
                's_no': idx + 1,
                'date': r[0] if len(r) > 0 else '',
                'link_shift': r[1] if len(r) > 1 else '',
                'reply_shift': r[2] if len(r) > 2 else '',
                'c_f': r[3] if len(r) > 3 else '',
                'link': link,
                'author': r[5] if len(r) > 5 else '',
                'head': r[6] if len(r) > 6 else '',
                'untagged': r[7] if len(r) > 7 else '',
                'picked_status': r[8] if len(r) > 8 else '',
                'complaint_type': r[9] if len(r) > 9 else '',
                'discom': r[10] if len(r) > 10 else '',
                'zone': r[11] if len(r) > 11 else '',
                'district': r[12] if len(r) > 12 else '',
                'remark': r[13] if len(r) > 13 else '',
                'status': r[14] if len(r) > 14 else '',
                'reply_30': r[15] if len(r) > 15 else '',
                'reply_60': r[16] if len(r) > 16 else '',
                'complaint_no': r[17] if len(r) > 17 else '',
                'sts': r[18] if len(r) > 18 else '',
            }

print(f"Total non-empty manual posts: {len(manual_posts)}")

# 2. Fetch our automated DB
conn = sqlite3.connect('data/uppcl_monitor.db')
c = conn.cursor()
c.execute('SELECT post_id, author_username, picked_status, complaint_type, discom, zone, district, text, created_at_utc FROM processed_posts')
db_posts = {}
for r in c.fetchall():
    db_posts[r[0]] = {
        'post_id': r[0],
        'author': r[1],
        'picked_status': r[2],
        'complaint_type': r[3],
        'discom': r[4],
        'zone': r[5],
        'district': r[6],
        'text': r[7],
        'created_at_utc': r[8]
    }
conn.close()

print(f"Total automated DB posts: {len(db_posts)}")

overlap = set(manual_posts.keys()).intersection(set(db_posts.keys()))
print(f"Direct overlapping post IDs: {len(overlap)}")

# Compare overlapping posts in detail
print("\n" + "="*80)
print(f"DETAILED FIELD COMPARISON ON {len(overlap)} MATCHING POSTS:")
print("="*80)

for p_id in sorted(overlap):
    m = manual_posts[p_id]
    d = db_posts[p_id]
    print(f"\n[Post ID: {p_id}] Author: @{m['author']} (Manual Row {m['row']}, S.No {m['s_no']})")
    print(f"  Field            | Manual Sheet             | Automated Engine")
    print(f"  -----------------+--------------------------+---------------------------")
    print(f"  Picked Status    | {m['picked_status']:<24} | {d['picked_status']}")
    print(f"  Complaint Type   | {m['complaint_type']:<24} | {d['complaint_type']}")
    print(f"  DISCOM           | {m['discom']:<24} | {d['discom']}")
    print(f"  Zone             | {m['zone']:<24} | {d['zone']}")
    print(f"  District         | {m['district']:<24} | {d['district']}")
    print(f"  FULL TEXT: {d['text']}")
