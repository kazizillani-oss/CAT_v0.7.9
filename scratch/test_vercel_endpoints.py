import urllib.request

for path in ['/', '/health', '/api/diag', '/api/status']:
    url = f'https://cat-v0-7-9.vercel.app{path}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"{path}: status {resp.status}, body: {resp.read()[:200]}")
    except urllib.error.HTTPError as e:
        print(f"{path}: HTTPError {e.code}, body: {e.read()[:200]}")
    except Exception as e:
        print(f"{path}: Error {e}")
