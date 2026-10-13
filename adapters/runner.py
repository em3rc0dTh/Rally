"""Supervised periodic connector process. One source credential per process/tenant."""
import asyncio
import logging
import os
import signal
from adapters.transport import RallyClient


async def main():
    source = os.environ['RALLY_CONNECTOR']
    if source == 'odoo':
        from adapters.odoo_sync_cli import main as cycle
    elif source == 'traccar':
        from adapters.ingest_cli import main as cycle
    else:
        raise ValueError('RALLY_CONNECTOR must be odoo or traccar')
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('rally.connector')
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    interval = max(15, int(os.getenv('RALLY_CONNECTOR_SECONDS', '60')))
    while not stop.is_set():
        try:
            await cycle()
        except Exception as error:
            detail = 'Connector cycle failed: ' + type(error).__name__
            log.error(detail)
            try:
                await RallyClient().heartbeat('error', detail)
            except Exception:
                log.error('Heartbeat unavailable; dashboard will show stale coverage')
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


if __name__ == '__main__':
    asyncio.run(main())
