import urllib.request
import json

url = 'https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/runs?per_page=10'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        for r in data.get('workflow_runs', []):
            print(f"{r['name']}: {r['head_sha'][:7]} - status: {r['status']}, conclusion: {r['conclusion']}, run: {r['html_url']}")
except Exception as e:
    print('Error:', e)
