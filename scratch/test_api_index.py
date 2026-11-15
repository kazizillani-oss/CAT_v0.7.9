import sys
sys.path.insert(0, '.')
from starlette.testclient import TestClient
from api.index import app

client = TestClient(app)
resp = client.get('/')
print("GET / status:", resp.status_code)
print("GET / length:", len(resp.content))
print("GET / content preview:", resp.text[:200])

resp_diag = client.get('/api/diag')
print("GET /api/diag status:", resp_diag.status_code)
print("GET /api/diag json:", resp_diag.json())
