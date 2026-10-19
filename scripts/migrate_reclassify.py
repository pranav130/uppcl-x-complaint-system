import sys
sys.stdout.reconfigure(encoding='utf-8')
import sqlite3
from uppcl_x_automation.classifier import GrievanceClassifier

classifier = GrievanceClassifier()
conn = sqlite3.connect('data/uppcl_monitor.db')
c = conn.cursor()

c.execute("SELECT post_id, author_username, text, picked_status, complaint_type FROM processed_posts")
all_posts = c.fetchall()
print(f"Total posts inspected in DB: {len(all_posts)}")

updated_count = 0
for post_id, author, text, old_status, old_type in all_posts:
    res = classifier.classify(text=text, author_username=author)
    if res.picked_status != old_status or res.complaint_type != old_type:
        updated_count += 1
        print(f"Post {post_id} (@{author}):")
        print(f"  BEFORE: status={old_status}, type={old_type}")
        print(f"  AFTER:  status={res.picked_status}, type={res.complaint_type}")
        c.execute(
            "UPDATE processed_posts SET picked_status = ?, complaint_type = ? WHERE post_id = ?",
            (res.picked_status, res.complaint_type, post_id)
        )

conn.commit()
conn.close()
print(f"\nMigration complete. Updated {updated_count} records in SQLite DB.")
