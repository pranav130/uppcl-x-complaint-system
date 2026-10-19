import sys
sys.stdout.reconfigure(encoding='utf-8')
import os, csv, io, json, re, time
import requests
from dotenv import load_dotenv

from uppcl_x_automation.config import load_config
from uppcl_x_automation.classifier import GrievanceClassifier
from uppcl_x_automation.router import DiscomRouter

load_dotenv()
config = load_config()
classifier = GrievanceClassifier()
router = DiscomRouter(config)

bearer_token = os.getenv("X_BEARER_TOKEN")
if not bearer_token:
    print("Error: No X_BEARER_TOKEN found in .env")
    sys.exit(1)

# 1. Fetch manual sheet
manual_url = "https://docs.google.com/spreadsheets/d/1shjWcK69y0S7pIHI-2V5Wh6c2SSSQBKcpgprmPbeNe8/export?format=csv&gid=283417465"
resp = requests.get(manual_url)
if resp.status_code != 200:
    print(f"Error fetching manual sheet: HTTP {resp.status_code}")
    sys.exit(1)

manual_rows = list(csv.reader(io.StringIO(resp.text)))[2:]

manual_records = []
post_ids = []

for idx, r in enumerate(manual_rows):
    if len(r) > 4 and r[4].strip():
        link = r[4].strip()
        m = re.search(r"status/(\d+)", link)
        if m:
            p_id = m.group(1)
            manual_records.append({
                "row_num": idx + 3,
                "s_no": idx + 1,
                "date": r[0] if len(r) > 0 else "",
                "shift": r[1] if len(r) > 1 else "",
                "cf": r[3] if len(r) > 3 else "",
                "link": link,
                "post_id": p_id,
                "author": r[5].strip().lstrip("@") if len(r) > 5 else "",
                "head": r[6].strip() if len(r) > 6 else "",
                "picked_status": r[8].strip() if len(r) > 8 else "",
                "complaint_type": r[9].strip() if len(r) > 9 else "",
                "discom": r[10].strip() if len(r) > 10 else "",
                "zone": r[11].strip() if len(r) > 11 else "",
                "district": r[12].strip() if len(r) > 12 else "",
                "status": r[14].strip() if len(r) > 14 else "",
                "reply_30": r[15].strip() if len(r) > 15 else ""
            })
            post_ids.append(p_id)

unique_ids = list(dict.fromkeys(post_ids))
print(f"Loaded {len(manual_records)} manual entries ({len(unique_ids)} unique post IDs).")

# 2. Batch fetch tweets via X API v2 (chunks of 100)
headers = {"Authorization": f"Bearer {bearer_token}"}
tweets_by_id = {}

for i in range(0, len(unique_ids), 100):
    chunk = unique_ids[i:i+100]
    chunk_str = ",".join(chunk)
    url = f"https://api.x.com/2/tweets?ids={chunk_str}&tweet.fields=id,text,author_id,created_at,entities&expansions=author_id&user.fields=id,name,username,location"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        for tw in data.get("data", []):
            author_data = users.get(tw.get("author_id"), {})
            mentions = [f"@{m.get('username')}" for m in tw.get("entities", {}).get("mentions", [])]
            tweets_by_id[tw["id"]] = {
                "id": tw["id"],
                "text": tw["text"],
                "author_username": author_data.get("username", ""),
                "author_location": author_data.get("location", ""),
                "mentions": mentions,
                "created_at": tw.get("created_at")
            }
    else:
        print(f"X API error on chunk {i}: HTTP {r.status_code} - {r.text}")

print(f"Successfully retrieved {len(tweets_by_id)} tweets from X API.\n")

# 3. Cross-benchmark comparison
comparison_results = []
metrics = {
    "total_evaluated": 0,
    "picked_status_exact": 0,
    "picked_status_discrepancy": 0,
    "complaint_type_exact": 0,
    "discom_exact": 0,
    "discom_automated_identified_when_manual_empty": 0,
    "district_exact": 0,
    "district_automated_identified_when_manual_empty": 0,
}

for rec in manual_records:
    pid = rec["post_id"]
    tw = tweets_by_id.get(pid)
    if not tw:
        continue

    metrics["total_evaluated"] += 1

    # Run Automated Pipeline
    c_res = classifier.classify(
        text=tw["text"],
        mentioned_accounts=tw["mentions"],
        author_username=tw["author_username"] or rec["author"]
    )
    r_res = router.route(
        text=tw["text"],
        mentioned_handles=tw["mentions"],
        author_location=tw["author_location"]
    )

    m_picked = rec["picked_status"].upper()
    a_picked = c_res.picked_status.upper()

    m_type = rec["complaint_type"].upper()
    a_type = c_res.complaint_type.upper()

    m_discom = rec["discom"].upper()
    a_discom = (r_res.discom or "").upper()
    # Normalize KESCO spelling
    if m_discom == "KESCO": m_discom = "KESCO"
    if a_discom == "KESCO": a_discom = "KESCO"

    m_dist = rec["district"].upper()
    a_dist = (r_res.district or "").upper()

    # Track metrics
    if m_picked == a_picked:
        metrics["picked_status_exact"] += 1
    else:
        metrics["picked_status_discrepancy"] += 1

    if m_type == a_type:
        metrics["complaint_type_exact"] += 1

    if m_discom and a_discom and m_discom == a_discom:
        metrics["discom_exact"] += 1
    elif not m_discom and a_discom:
        metrics["discom_automated_identified_when_manual_empty"] += 1

    if m_dist and a_dist and m_dist in a_dist or a_dist in m_dist:
        metrics["district_exact"] += 1
    elif not m_dist and a_dist:
        metrics["district_automated_identified_when_manual_empty"] += 1

    comparison_results.append({
        "s_no": rec["s_no"],
        "post_id": pid,
        "author": rec["author"] or tw["author_username"],
        "m_picked": m_picked, "a_picked": a_picked,
        "m_type": m_type, "a_type": a_type,
        "m_discom": m_discom, "a_discom": a_discom,
        "m_dist": m_dist, "a_dist": a_dist,
        "text": tw["text"]
    })

print("="*80)
print("BENCHMARK COMPARISON SUMMARY: MANUAL SHEET vs AUTOMATED SYSTEM")
print("="*80)
print(f"Total Evaluated Posts:                      {metrics['total_evaluated']}")
print(f"Picked Status Agreement:                    {metrics['picked_status_exact']}/{metrics['total_evaluated']} ({metrics['picked_status_exact']/metrics['total_evaluated']*100:.1f}%)")
print(f"Complaint Type Exact Matches:               {metrics['complaint_type_exact']}/{metrics['total_evaluated']} ({metrics['complaint_type_exact']/metrics['total_evaluated']*100:.1f}%)")
print(f"DISCOM Exact Matches (when both filled):    {metrics['discom_exact']}")
print(f"DISCOM Found by AI (when manual was empty): {metrics['discom_automated_identified_when_manual_empty']}")
print(f"District Found by AI (when manual empty):   {metrics['district_automated_identified_when_manual_empty']}")

# Show samples of interesting discrepancies or advantages of automation
print("\n" + "="*80)
print("SAMPLE DETAILED ROW COMPARISONS:")
print("="*80)
for r in comparison_results[:15]:
    status_match = "MATCH" if r["m_picked"] == r["a_picked"] else "DIFF"
    type_match = "MATCH" if r["m_type"] == r["a_type"] else "DIFF"
    discom_match = "MATCH" if r["m_discom"] == r["a_discom"] else "DIFF"
    print(f"S.No {r['s_no']} (@{r['author']}):")
    print(f"  Picked Status:  Manual=[{r['m_picked']}] | Auto=[{r['a_picked']}] ({status_match})")
    print(f"  Complaint Type: Manual=[{r['m_type']}] | Auto=[{r['a_type']}] ({type_match})")
    print(f"  DISCOM:         Manual=[{r['m_discom']}] | Auto=[{r['a_discom']}] ({discom_match})")
    print(f"  District:       Manual=[{r['m_dist']}] | Auto=[{r['a_dist']}]")
    print(f"  Text: {repr(r['text'][:80])}")
    print()
