import asyncio
import logging

import edgedb

from aiohttp import web

log = logging.getLogger(__name__)


async def _connect(app: web.Application) -> None:
    log.debug("connecting to edgedb")

    app["edgedb"] = await edgedb.create_async_pool(**app["config"]["edgedb"])
    app["edgedb_ready"].set()


async def _disconnect(app: web.Application) -> None:
    log.debug("disconnecting from edgedb")

    app["edgedb_ready"].clear()
    await app["edgedb"].aclose()


def setup(app: web.Application) -> None:
    # useless without reconnect logic
    app["edgedb_ready"] = asyncio.Event()

    app.on_startup.append(_connect)
    app.on_cleanup.append(_disconnect)
