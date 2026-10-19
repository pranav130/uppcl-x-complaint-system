import sys
sys.stdout.reconfigure(encoding='utf-8')
from collections import Counter
from uppcl_x_automation.config import load_config
from uppcl_x_automation.classifier import GrievanceClassifier
import csv, io, requests, re, os
from dotenv import load_dotenv

load_dotenv()
config = load_config()
classifier = GrievanceClassifier()
bearer_token = os.getenv('X_BEARER_TOKEN')

url = 'https://docs.google.com/spreadsheets/d/1shjWcK69y0S7pIHI-2V5Wh6c2SSSQBKcpgprmPbeNe8/export?format=csv&gid=283417465'
resp = requests.get(url)
manual_rows = list(csv.reader(io.StringIO(resp.text)))[2:203]

pids = []
for r in manual_rows:
    if len(r) > 4 and r[4]:
        m = re.search(r'status/(\d+)', r[4])
        if m:
            pids.append(m.group(1))
unique_pids = list(dict.fromkeys(pids))

headers = {'Authorization': f'Bearer {bearer_token}'}
tweets = {}
for i in range(0, len(unique_pids), 100):
    chunk = unique_pids[i:i+100]
    ids_str = ",".join(chunk)
    r = requests.get(f'https://api.x.com/2/tweets?ids={ids_str}&tweet.fields=id,text,entities', headers=headers)
    if r.status_code == 200:
        for t in r.json().get('data', []):
            tweets[t['id']] = t

discrepancies = []
for r in manual_rows:
    if len(r) > 4 and r[4]:
        m = re.search(r'status/(\d+)', r[4])
        if m and m.group(1) in tweets:
            pid = m.group(1)
            t = tweets[pid]
            mentions = [f"@{x['username']}" for x in t.get('entities', {}).get('mentions', [])]
            res = classifier.classify(text=t['text'], mentioned_accounts=mentions, author_username=r[5])
            m_type = r[9].strip().upper()
            a_type = res.complaint_type.upper()
            if m_type != a_type:
                discrepancies.append((m_type, a_type, t['text']))

counts = Counter((m, a) for m, a, _ in discrepancies)
print('Top Type Discrepancies (Manual vs Auto):')
for (m, a), cnt in counts.most_common(12):
    print(f'  Manual=[{m:<24}] vs Auto=[{a:<24}] : {cnt} times')

print('\nSamples of Manual=SUPPLY_OUTAGE vs Auto=INFO_AND_SUGG:')
for m, a, txt in [d for d in discrepancies if d[0]=='SUPPLY_OUTAGE' and d[1]=='INFO_AND_SUGG'][:5]:
    print('  Text:', repr(txt[:120]))

print('\nSamples of Manual=DISSATISFIED_CONSUMER vs Auto=INFO_AND_SUGG:')
for m, a, txt in [d for d in discrepancies if d[0]=='DISSATISFIED_CONSUMER' and d[1]=='INFO_AND_SUGG'][:5]:
    print('  Text:', repr(txt[:120]))

print('\nSamples of Manual=POLE_RELATED vs Auto=INFO_AND_SUGG:')
for m, a, txt in [d for d in discrepancies if d[0]=='POLE_RELATED' and d[1]=='INFO_AND_SUGG'][:5]:
    print('  Text:', repr(txt[:120]))
