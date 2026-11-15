import urllib.request
import json

url = 'https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/runs/43719706844/jobs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        for j in data.get('jobs', []):
            print(f"Job {j['name']}: status={j['status']}, conclusion={j['conclusion']}")
            for s in j.get('steps', []):
                if s['status'] == 'in_progress':
                    print(f"  Step in_progress: {s['name']}")
                elif s['conclusion'] == 'failure':
                    print(f"  Step failed: {s['name']}")
except Exception as e:
    print('Error:', e)
