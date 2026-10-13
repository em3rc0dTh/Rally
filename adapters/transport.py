"""Bounded replay of idempotent imports and immutable observations."""
import asyncio
import os
from urllib.parse import urlparse
import httpx


def validate_url(url):
    parsed = urlparse(url)
    local = parsed.hostname in {'localhost', '127.0.0.1', '::1'}
    internal = os.getenv('RALLY_ALLOW_INTERNAL_HTTP') == '1'
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Endpoint must be an origin without credentials, query or fragment')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and (local or internal)):
        raise ValueError('HTTPS required; explicitly allow HTTP only on a trusted private network')
    return url.rstrip('/')


async def request(client, method, url, **kwargs):
    for attempt in range(5):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt == 4:
                response.raise_for_status()
                return response
        except httpx.TransportError:
            if attempt == 4:
                raise
        await asyncio.sleep(min(2 ** attempt, 16))


class RallyClient:
    def __init__(self):
        self.base = validate_url(os.environ['RALLY_URL'])
        self.token = os.environ['RALLY_TENANT_TOKEN']

    async def post(self, path, body):
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await request(client, 'POST', self.base + '/api/' + path,
                                     headers={'Authorization': 'Bearer ' + self.token}, json=body)
            return response.json()

    async def heartbeat(self, status, detail=''):
        await self.post('connectors/heartbeat', {'status': status, 'detail': detail})
