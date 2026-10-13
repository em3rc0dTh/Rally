"""Bound requests before parsing; do not log secrets or request bodies."""
import json
import logging
import os
import re
import time
from collections import OrderedDict
from uuid import uuid4
from starlette.responses import JSONResponse

log = logging.getLogger('rally.http')


def validate_environment():
    secret = os.getenv('RALLY_ADMIN_KEY', '')
    if len(secret) < 32 or secret.lower().startswith(('change', 'replace', 'example')):
        raise RuntimeError('RALLY_ADMIN_KEY must contain a strong random secret of at least 32 characters')
    if os.getenv('RALLY_ENV') == 'production':
        if not os.getenv('RALLY_DATABASE_URL', '').startswith(('postgresql://', 'postgres://')):
            raise RuntimeError('Production requires RALLY_DATABASE_URL with PostgreSQL')
        hosts = os.getenv('RALLY_ALLOWED_HOSTS', '')
        if not hosts or '*' in hosts:
            raise RuntimeError('Production requires explicit RALLY_ALLOWED_HOSTS')
    for key, default in [('RALLY_RATE_PER_MINUTE', '600'), ('RALLY_BODY_LIMIT', '131072')]:
        if int(os.getenv(key, default)) < 1:
            raise RuntimeError(f'{key} must be positive')


class GuardMiddleware:
    def __init__(self, app):
        self.app = app
        self.windows = OrderedDict()
        self.limit = int(os.getenv('RALLY_RATE_PER_MINUTE', '600'))
        self.body_limit = int(os.getenv('RALLY_BODY_LIMIT', '131072'))

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = str(uuid4())
        path = scope['path']
        status = 500

        async def output(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = list(message.get('headers', []))
                headers.extend([
                    (b'x-request-id', request_id.encode()), (b'x-content-type-options', b'nosniff'),
                    (b'x-frame-options', b'DENY'), (b'referrer-policy', b'no-referrer'),
                    (b'cache-control', b'no-store'),
                    (b'content-security-policy', (b"default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; frame-ancestors 'none'" if path.startswith('/docs') and os.getenv('RALLY_ENV') != 'production' else b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")),
                    (b'permissions-policy', b'camera=(), microphone=(), geolocation=()'),
                ])
                if os.getenv('RALLY_ENV') == 'production':
                    headers.append((b'strict-transport-security', b'max-age=31536000'))
                message['headers'] = headers
            await send(message)

        async def reject(code, detail, headers=None):
            await JSONResponse({'detail': detail, 'request_id': request_id}, code, headers=headers)(scope, receive, output)

        if path.startswith('/api/'):
            # IP limiter is intentionally independent of user-controlled bearer strings.
            # Configure proxy trust explicitly; never trust arbitrary Forwarded headers.
            ip = (scope.get('client') or ('unknown',))[0]
            window = int(time.monotonic() // 60)
            bucket = (ip, 'admin' if path.startswith('/api/tenants') else 'api')
            prior, count = self.windows.get(bucket, (window, 0))
            count = count + 1 if prior == window else 1
            self.windows[bucket] = (window, count)
            self.windows.move_to_end(bucket)
            while len(self.windows) > 10000:
                self.windows.popitem(last=False)
            if count > (10 if bucket[1] == 'admin' else self.limit):
                return await reject(429, 'Rate limit exceeded', {'Retry-After': '60'})
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > self.body_limit:
                return await reject(413, 'Request body too large')
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        used = False

        async def buffered():
            nonlocal used
            if not used:
                used = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()

        try:
            await self.app(scope, buffered, output)
        finally:
            log.info(json.dumps({'request_id': request_id, 'method': scope['method'],
                                 'path': re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27,}', ':id', path)[:180],
                                 'status': status, 'duration_ms': round((time.monotonic()-started)*1000)}))
