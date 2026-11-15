import urllib.request
import json

url = 'https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/runs/43717921441/jobs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        for j in data.get('jobs', []):
            if j['conclusion'] == 'failure':
                print(f"Failed job ID: {j['id']} ({j['name']})")
                print(f"URL: {j['html_url']}")
except Exception as e:
    print('Error:', e)
