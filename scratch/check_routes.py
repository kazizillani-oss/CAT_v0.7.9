import sys
sys.path.insert(0, '.')
from calc_terminal.web.server import app

print("Total routes:", len(app.routes))
for r in app.routes:
    if hasattr(r, 'path') and r.path in ('/', '/api/diag', '/health', '/api/health'):
        print(f"Route: {r.path} -> {getattr(r, 'name', '')} {getattr(r, 'methods', '')}")
