import asyncio
import traceback
import sys

async def run():
    try:
        sys.path.insert(0, ".")
        import api.index as idx
        
        scope = {
            'type': 'http',
            'http_version': '1.1',
            'method': 'GET',
            'path': '/',
            'raw_path': b'/',
            'query_string': b'',
            'headers': [(b'host', b'localhost')],
            'client': ('127.0.0.1', 12345),
            'server': ('127.0.0.1', 80),
        }
        
        messages = []
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}
            
        async def send(message):
            messages.append(message)
            
        await idx.app(scope, receive, send)
        print("ASGI Response messages:", messages)
    except Exception as e:
        print("ASGI Call Failed!")
        traceback.print_exc()

asyncio.run(run())
