import urllib.request
import json

jobs = [132828817666, 132828817936, 132828817917, 132828818029]

for jid in jobs:
    url = f"https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/check-runs/{jid}/annotations"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req) as resp:
            annos = json.loads(resp.read().decode("utf-8"))
            print(f"=== Annotations for job {jid} (count: {len(annos)}) ===")
            for a in annos:
                print(f"  {a.get('path')}:{a.get('start_line')} - [{a.get('annotation_level')}] {a.get('title')}: {a.get('message')}")
    except Exception as e:
        print(f"Error for {jid}: {e}")
