import urllib.request
import sys

def get_job_log(job_id, out_name):
    url = f"https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/jobs/{job_id}/logs"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            with open(out_name, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Wrote {len(content)} chars to {out_name}")
    except Exception as e:
        print(f"Error fetching log for {job_id}: {e}")

get_job_log(132828817936, "scratch/job_310_log.txt") # 3.10
get_job_log(132828818029, "scratch/job_312_log.txt") # 3.12
