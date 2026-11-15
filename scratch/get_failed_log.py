import urllib.request

url = 'https://api.github.com/repos/kazizillani-oss/CAT_v0.7.9/actions/jobs/132823360313/logs'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as resp:
        log = resp.read().decode('utf-8', errors='replace')
        lines = [l for l in log.splitlines() if 'calc_terminal' in l or 'error' in l.lower() or 'flake8' in l.lower()]
        for l in lines[-30:]:
            print(l)
except Exception as e:
    print('Error:', e)
