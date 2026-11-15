import urllib.request
import json
import sys

run_id = "43719706844"
url = f"https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/runs/{run_id}/jobs"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"})

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))

for j in data.get("jobs", []):
    print(f"=== Job: {j['name']} (id: {j['id']}, conclusion: {j['conclusion']}) ===")
    for s in j.get("steps", []):
        if s.get("conclusion") == "failure":
            print(f"  FAILED STEP: {s['name']}")
