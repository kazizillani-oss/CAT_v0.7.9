import urllib.request
import json

url = 'https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/runs/43717921441/jobs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        for j in data.get('jobs', []):
            print(f"Job: {j['name']}, ID: {j['id']}, conclusion: {j['conclusion']}")
            annot_url = f"https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/check-runs/{j['id']}/annotations"
            try:
                areq = urllib.request.Request(annot_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(areq) as aresp:
                    adata = json.loads(aresp.read().decode('utf-8'))
                    for a in adata:
                        print(f"  Annotation: {a.get('message')}")
            except Exception as e:
                pass
except Exception as e:
    print('Error:', e)
